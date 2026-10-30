#!/usr/bin/env python3
"""Draft inventory.json from successful verification reports."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import secrets
import sys
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SUPPORT_PATH = ROOT / "support.json"
RELEASE_BASE = "https://github.com/BernieSumption/pg_binaries/releases/download"


class InventoryError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InventoryError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise InventoryError(f"{path} must contain a JSON object")
    return value


def make_inventory(reports: list[Path], tag: str, support: dict[str, Any], *,
                   today: str | None = None, suffix: str | None = None) -> dict[str, Any]:
    if not reports:
        raise InventoryError("at least one verification report is required")
    if not tag or "/" in tag or tag in (".", ".."):
        raise InventoryError("release tag must be a non-empty single path segment")
    packages_cfg = support.get("packages")
    targets_cfg = support.get("targets")
    if not isinstance(packages_cfg, dict) or not isinstance(targets_cfg, dict):
        raise InventoryError("support.json has no packages or targets map")

    postgresql = support.get("postgresql", {})
    pg_version = None

    os_support: dict[str, dict[str, str]] = {}
    package_downloads: dict[str, dict[str, dict[str, str]]] = {
        "postgresql": {}, **{name: {} for name in packages_cfg}}
    extension_defs: dict[str, dict[str, Any]] = {}
    builtin_targets: dict[str, set[str]] = {}
    package_names = set(packages_cfg)
    seen_targets: set[str] = set()

    for report_path in reports:
        report = _load(report_path)
        verified_version = report.get("postgresql_version")
        if not isinstance(verified_version, str) or not re.fullmatch(r"[0-9][a-zA-Z0-9._-]*", verified_version):
            raise InventoryError(f"{report_path}: missing verified PostgreSQL version")
        if pg_version is not None and pg_version != verified_version:
            raise InventoryError("PostgreSQL versions differ between targets")
        pg_version = verified_version
        target = report.get("target")
        if not isinstance(target, str) or target not in targets_cfg:
            raise InventoryError(f"{report_path}: unsupported target {target!r}")
        if target in seen_targets:
            raise InventoryError(f"duplicate verification report for {target}")
        seen_targets.add(target)
        combinations = report.get("combinations")
        expected_combinations = {"postgresql-only", "all-packages", *package_names}
        if (not isinstance(combinations, list)
                or len(combinations) != len(expected_combinations)
                or any(not isinstance(item, dict) or not isinstance(item.get("name"), str)
                       for item in combinations)
                or {item["name"] for item in combinations} != expected_combinations
                or any(item.get("outcome") != "passed"
                       for item in combinations)):
            raise InventoryError(f"{report_path}: every required verification combination must pass")
        archives = report.get("archives")
        expected = {"postgresql", *package_names}
        if not isinstance(archives, dict) or set(archives) != expected:
            raise InventoryError(f"{report_path}: archive records must include PostgreSQL and every selected package")
        support_target = targets_cfg[target]
        minimum = support_target.get("minimum_os_version")
        if not isinstance(minimum, str) or not minimum:
            raise InventoryError(f"support.json has no minimum OS version for {target}")
        os_name = target.split("-", 1)[0]
        if os_name not in os_support:
            os_support[os_name] = {"minimum_version": minimum}
        elif os_support[os_name]["minimum_version"] != minimum:
            raise InventoryError(f"inconsistent {os_name} minimum OS versions across targets")

        for component, record in archives.items():
            if not isinstance(record, dict):
                raise InventoryError(f"{report_path}: invalid archive record for {component}")
            filename, digest = record.get("filename"), record.get("sha256")
            expected_filename = (f"postgresql-{pg_version}-{target}.tar.gz" if component == "postgresql"
                                 else f"{component}-postgresql-{pg_version}-{target}.tar.gz")
            if filename != expected_filename:
                raise InventoryError(f"{report_path}: invalid archive filename for {component}")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise InventoryError(f"{report_path}: invalid archive checksum for {component}")
            package_downloads[component][target] = {
                "url": f"{RELEASE_BASE}/{quote(tag, safe='')}/{quote(filename, safe='')}",
                "sha256": digest,
            }

        builtins = report.get("postgresql_builtin_extensions")
        if (not isinstance(builtins, list) or not builtins
                or any(not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", name)
                       for name in builtins)
                or len(builtins) != len(set(builtins))):
            raise InventoryError(f"{report_path}: invalid PostgreSQL built-in extension list")
        for name in builtins:
            builtin_targets.setdefault(name, set()).add(target)

        for package_name, package in packages_cfg.items():
            for name, details in package.get("extensions", {}).items():
                version = report.get("extension_versions", {}).get(name)
                if not isinstance(version, str) or not version:
                    raise InventoryError(f"{report_path}: missing verified SQL version for {name}")
                entry: dict[str, Any] = {"package": package_name, "version": version}
                if details.get("config"):
                    entry["config"] = details["config"]
                _merge_extension(extension_defs, name, entry)

    if seen_targets != set(targets_cfg):
        raise InventoryError(f"missing verified targets: {sorted(set(targets_cfg) - seen_targets)}")
    for name, available in builtin_targets.items():
        entry: dict[str, Any] = {"package": "postgresql"}
        if available != seen_targets:
            entry["targets"] = sorted(available)
        _merge_extension(extension_defs, name, entry)

    result: dict[str, Any] = {
        "schema_version": 1,
        "inventory_version": f"{pg_version}-{today or datetime.now(timezone.utc).date().isoformat()}-{suffix or secrets.token_hex(4)}",
        "os_support": os_support,
        "postgresql": {"package": "postgresql", "version": pg_version},
        "packages": {},
        "extensions": extension_defs,
    }
    for name, config in [("postgresql", postgresql.get("config", {})),
                         *[(n, p.get("config", {})) for n, p in packages_cfg.items()]]:
        entry: dict[str, Any] = {"downloads": package_downloads[name]}
        if config:
            entry["config"] = config
        result["packages"][name] = entry
    return result


def _merge_extension(target: dict[str, dict[str, Any]], name: str, entry: dict[str, Any]) -> None:
    old = target.get(name)
    if old is not None and old != entry:
        raise InventoryError(f"conflicting inventory mapping for extension {name}")
    target[name] = entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path, help="successful verification-report.json files")
    parser.add_argument("--tag", required=True, help="GitHub release tag")
    parser.add_argument("--output", required=True, type=Path, help="new inventory JSON path")
    parser.add_argument("--support", type=Path, default=SUPPORT_PATH)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise InventoryError(f"output already exists: {args.output}")
        from build_support.metadata import load_selection
        inventory = make_inventory(args.reports, args.tag, load_selection(args.support))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    except (InventoryError, OSError) as error:
        print(f"inventory draft failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
