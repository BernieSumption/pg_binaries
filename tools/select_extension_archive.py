#!/usr/bin/env python3
"""Select the inventory archive serving one exact extension target."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys

_SPEC = importlib.util.spec_from_file_location(
    "selector_coverage", Path(__file__).with_name("coverage.py"))
_coverage = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_coverage)


class SelectionError(ValueError):
    pass


def select_archive(inventory, support, postgresql_version, platform, project,
                   extension_version, sql_name):
    """Return the unique download for a project SQL name on an exact PG target."""
    try:
        target = _coverage.version_parts(postgresql_version, "selected PostgreSQL version")
    except _coverage.CoverageError as exc:
        raise SelectionError(str(exc)) from exc

    projects = support.get("extensions", {}) if isinstance(support, dict) else {}
    if project not in projects:
        raise SelectionError(f"unknown extension project {project!r}")
    project_details = projects[project]
    if sql_name not in project_details.get("sql_names", []):
        raise SelectionError(f"SQL name {sql_name!r} is not declared by project {project!r}")
    if extension_version not in project_details.get("versions", {}):
        raise SelectionError(f"extension version {extension_version!r} is not declared by project {project!r}")

    try:
        _, downloads = _coverage.inventory_targets(inventory)
    except _coverage.CoverageError as exc:
        if "overlapping PostgreSQL ranges" in str(exc):
            raise SelectionError("ambiguous extension archive ranges in inventory") from exc
        raise SelectionError(str(exc)) from exc

    candidates, out_of_range = [], []
    for (name, version, low, high, entry_platform), download in downloads.items():
        if name != sql_name or version != extension_version or entry_platform != platform:
            continue
        try:
            bounds = (_coverage.version_parts(low, "inventory range"),
                      _coverage.version_parts(high, "inventory range"))
        except _coverage.CoverageError as exc:
            raise SelectionError(str(exc)) from exc
        if bounds[0] <= target <= bounds[1]:
            candidates.append((version, download))
        else:
            out_of_range.append((version, low, high))
    if len(candidates) > 1:
        raise SelectionError(f"ambiguous archives for {project}/{sql_name} PostgreSQL {postgresql_version} {platform}")
    if not candidates:
        if out_of_range:
            raise SelectionError(f"{project}/{sql_name} has no archive covering PostgreSQL {postgresql_version} on {platform}")
        raise SelectionError(f"no archive for {project}/{sql_name} on {platform}")
    return candidates[0][1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--extension-version", required=True)
    parser.add_argument("--sql-name", required=True)
    args = parser.parse_args()
    try:
        root = args.root
        inventory = _coverage.load_json(root / "inventory.json")
        support = _coverage.load_json(root / "support.json")
        print(json.dumps(select_archive(inventory, support, args.postgresql_version,
                                        args.platform, args.project,
                                        args.extension_version, args.sql_name), sort_keys=True))
        return 0
    except (SelectionError, _coverage.CoverageError) as exc:
        print(f"select-extension-archive: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
