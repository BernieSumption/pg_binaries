#!/usr/bin/env python3
"""Check release metadata and local archive bytes before publication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import quote

from verification.archive import ArchiveError, read_archive
from verification.inventory import RELEASE_BASE
from verification.records import RecordError, sha256_file

ROOT = Path(__file__).resolve().parents[1]


class PreflightError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreflightError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreflightError(f"{path} must contain a JSON object")
    return value


def check(inventory_path: Path, pairs: list[tuple[str, Path, Path]], support_path: Path) -> int:
    inventory, support = _load(inventory_path), _load(support_path)
    packages = support.get("packages")
    targets = support.get("targets")
    if not isinstance(packages, dict) or not isinstance(targets, dict):
        raise PreflightError("support.json must define packages and targets")
    expected_components = {"postgresql", *packages}
    seen: set[str] = set()
    extension_map = inventory.get("extensions")
    downloads = inventory.get("packages")
    if not isinstance(extension_map, dict) or not isinstance(downloads, dict):
        raise PreflightError("inventory must define extensions and packages")
    if set(downloads) != expected_components:
        raise PreflightError("inventory packages must match the selected components")
    for target, selection_path, report_path in pairs:
        if target not in targets or target in seen:
            raise PreflightError(f"unsupported or duplicate target: {target}")
        seen.add(target)
        selection, report = _load(selection_path), _load(report_path)
        if report.get("target") != target or selection.get("target") != target:
            raise PreflightError(f"report or selection target does not match {target}")
        combos = report.get("combinations")
        expected_combos = {"postgresql-only", "all-packages", *packages}
        if (not isinstance(combos, list) or {c.get("name") for c in combos if isinstance(c, dict)} != expected_combos
                or len(combos) != len(expected_combos)
                or any(not isinstance(c, dict) or c.get("outcome") != "passed" for c in combos)):
            raise PreflightError(f"{report_path}: every verification combination must pass")
        archives, selected = report.get("archives"), selection.get("components")
        if not isinstance(archives, dict) or set(archives) != expected_components:
            raise PreflightError(f"{report_path}: archive records must include every component")
        if not isinstance(selected, dict) or set(selected) != expected_components:
            raise PreflightError(f"{selection_path}: selection must include every component")
        builtin_names = report.get("postgresql_builtin_extensions")
        if (not isinstance(builtin_names, list) or not builtin_names
                or any(not isinstance(name, str) for name in builtin_names)
                or len(builtin_names) != len(set(builtin_names))):
            raise PreflightError(f"{report_path}: invalid built-in extension list")
        inventory_builtins = {name for name, item in extension_map.items()
                              if isinstance(item, dict) and item.get("package") == "postgresql"
                              and ("targets" not in item or target in item["targets"])}
        if set(builtin_names) != inventory_builtins:
            raise PreflightError(f"{target}: inventory PostgreSQL extensions do not match verification report")

        for component in expected_components:
            record, item = archives[component], selected[component]
            if not isinstance(record, dict) or not isinstance(item, dict):
                raise PreflightError(f"{target}: invalid archive selection for {component}")
            digest, path_value = record.get("sha256"), item.get("archive")
            archive_path = Path(path_value) if isinstance(path_value, str) else Path()
            if (not isinstance(digest, str) or item.get("sha256") != digest
                    or not isinstance(item.get("origin_run"), int) or item["origin_run"] <= 0
                    or item.get("origin_run") != record.get("origin_run")
                    or record.get("filename") != archive_path.name):
                raise PreflightError(f"{target}: selection and report disagree for {component}")
            try:
                actual = sha256_file(archive_path)
                contents = read_archive(archive_path)
            except (RecordError, ArchiveError) as exc:
                raise PreflightError(f"{target}: invalid {component} archive: {exc}") from exc
            if actual != digest:
                raise PreflightError(f"{target}: archive SHA-256 mismatch for {component}")
            prefix = "postgresql/share/postgresql/extension/"
            controls = {path[len(prefix):-len(".control")] for path, entry in contents.items()
                        if path.startswith(prefix) and path.endswith(".control")
                        and "/" not in path[len(prefix):] and entry.kind == "file"}
            expected_controls = (set(builtin_names) if component == "postgresql"
                                 else set(packages[component].get("extensions", {})))
            if controls != expected_controls:
                raise PreflightError(f"{target}: {component} archive control files differ from selected SQL extensions")
            try:
                download = downloads[component]["downloads"][target]
            except (KeyError, TypeError):
                raise PreflightError(f"inventory has no download for {component} on {target}") from None
            url = download.get("url") if isinstance(download, dict) else None
            tail = url.removeprefix(RELEASE_BASE + "/").split("/") if isinstance(url, str) else []
            if (not isinstance(download, dict) or download.get("sha256") != digest
                    or not isinstance(url, str) or not url.startswith(RELEASE_BASE + "/")
                    or len(tail) != 2 or not tail[0]
                    or tail[1] != quote(archive_path.name, safe="")):
                raise PreflightError(f"inventory download does not match verified {component} archive on {target}")

    if seen != set(targets):
        raise PreflightError(f"missing targets: {sorted(set(targets) - seen)}")
    for component, record in downloads.items():
        if not isinstance(record, dict) or set(record.get("downloads", {})) != seen:
            raise PreflightError(f"inventory has extra or missing targets for {component}")
    for name, item in extension_map.items():
        if not isinstance(item, dict) or item.get("package") not in expected_components:
            raise PreflightError(f"invalid package mapping for extension {name}")
        if item["package"] != "postgresql" and name not in packages[item["package"]].get("extensions", {}):
            raise PreflightError(f"inventory maps extension {name} to the wrong package")
    for package, config in packages.items():
        extension_names = config.get("extensions", {}) if isinstance(config, dict) else {}
        for name in extension_names:
            mapping = extension_map.get(name)
            if not isinstance(mapping, dict) or mapping.get("package") != package:
                raise PreflightError(f"inventory does not map extension {name} to package {package}")
    return len(seen)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--target", action="append", required=True, metavar="TARGET=SELECTION.json,REPORT.json",
                        help="pair selection and verification reports; repeat for each target")
    parser.add_argument("--support", type=Path, default=ROOT / "support.json")
    args = parser.parse_args(argv)
    pairs = []
    for value in args.target:
        target, sep, files = value.partition("=")
        selection, comma, report = files.partition(",")
        if not sep or not comma or not target or not selection or not report:
            parser.error(f"invalid --target value: {value!r}")
        pairs.append((target, Path(selection), Path(report)))
    try:
        count = check(args.inventory, pairs, args.support)
    except PreflightError as exc:
        print(f"publication preflight failed: {exc}", file=sys.stderr)
        return 1
    print(f"publication preflight passed for {count} target(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
