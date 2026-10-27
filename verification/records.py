#!/usr/bin/env python3
"""Write build records from support.json and the produced archive bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional


class RecordError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RecordError(f"cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def _source_list(value: Any) -> list[dict[str, str]]:
    """Find selected downloadable sources in a support.json subtree."""
    found: list[dict[str, str]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("url"), str) and isinstance(node.get("sha256"), str):
                item = {key: node[key] for key in ("project", "version", "url", "sha256")
                        if isinstance(node.get(key), str)}
                found.append(item)
                return
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return found


def selected_inputs(support: dict[str, Any], target: str,
                    component: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if target not in support.get("targets", {}):
        raise RecordError(f"unsupported target: {target}")
    selection = (support.get("postgresql") if component == "postgresql"
                 else support.get("packages", {}).get(component))
    if not isinstance(selection, dict):
        raise RecordError(f"unknown component: {component}")
    build_inputs = selection.get("build_inputs", {}).get(target, {})
    source_tree = ({"source": selection.get("source", {}), "build_inputs": build_inputs}
                   if component == "postgresql" else
                   {"sources": selection.get("sources", []), "build_inputs": build_inputs})
    sources = _source_list(source_tree)
    if not sources:
        raise RecordError(f"no selected downloadable sources found for {component} on {target}")
    return sources, build_inputs


def make_record(support_path: Path, target: str, component: str,
                archive_path: Path, revision: str,
                postgresql_archive: Optional[Path] = None,
                development_archive: Optional[Path] = None) -> dict[str, Any]:
    try:
        support = json.loads(support_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecordError(f"cannot read support file {support_path}: {exc}") from exc

    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise RecordError("Git revision must be a full lowercase commit hash")

    if component == "postgresql":
        if postgresql_archive is not None:
            raise RecordError("PostgreSQL records do not take --postgresql-archive")
    else:
        if postgresql_archive is None:
            raise RecordError("extension records require --postgresql-archive")
        if development_archive is not None:
            raise RecordError("extension records do not take --development-archive")
    sources, build_inputs = selected_inputs(support, target, component)

    record: dict[str, Any] = {
        "schema_version": 1,
        "component": component,
        "target": target,
        "git_revision": revision.strip(),
        "sources": sources,
        "build_inputs": build_inputs,
        "archive": {"filename": archive_path.name, "sha256": sha256_file(archive_path)},
    }
    if postgresql_archive is not None:
        record["postgresql_archive"] = {
            "filename": postgresql_archive.name,
            "sha256": sha256_file(postgresql_archive),
        }
    if development_archive is not None:
        record["development_archive"] = {
            "filename": development_archive.name,
            "sha256": sha256_file(development_archive),
        }
    return record


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--support", type=Path, default=Path(__file__).resolve().parents[1] / "support.json")
    parser.add_argument("--target", required=True)
    parser.add_argument("--component", required=True,
                        help="postgresql or a package key from support.json")
    parser.add_argument("--revision", required=True, help="Git commit revision")
    parser.add_argument("--archive", required=True, type=Path,
                        help="produced .tar.gz archive")
    parser.add_argument("--postgresql-archive", type=Path,
                        help="PostgreSQL archive used to compile an extension")
    parser.add_argument("--development-archive", type=Path,
                        help="PostgreSQL development archive produced alongside the runtime archive")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        record = make_record(args.support, args.target, args.component,
                             args.archive, args.revision, args.postgresql_archive,
                             args.development_archive)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    except (RecordError, OSError) as exc:
        print(f"build record failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
