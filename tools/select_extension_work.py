#!/usr/bin/env python3
"""Resolve one checked-in extension build selection against the work queue."""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_queue_spec = importlib.util.spec_from_file_location(
    "select_extension_work_queue", Path(__file__).with_name("extension_work_queue.py"))
extension_work_queue = importlib.util.module_from_spec(_queue_spec)
_queue_spec.loader.exec_module(extension_work_queue)


RUNNERS = {
    "linux-x86_64": "ubuntu-24.04",
    "linux-arm64": "ubuntu-24.04-arm",
    "macos-x86_64": "macos-15-intel",
    "macos-arm64": "macos-15",
    "windows-x86_64": "windows-2022",
}
REQUIRED = {"project", "version", "platform"}


def resolve(root, selection):
    if (not isinstance(selection, dict) or not REQUIRED <= set(selection)
            or set(selection) not in (REQUIRED | {"postgresql_major"},
                                     REQUIRED | {"postgresql_version"})):
        raise ValueError("selection must contain project, version, platform, and exactly one PostgreSQL major or exact version")
    if "postgresql_major" in selection:
        if not isinstance(selection["postgresql_major"], int) or isinstance(selection["postgresql_major"], bool):
            raise ValueError("postgresql_major must be an integer")
        target_match = lambda item: item.get("postgresql_major") == selection["postgresql_major"]
    else:
        pg_version = selection["postgresql_version"]
        if not isinstance(pg_version, str) or not pg_version:
            raise ValueError("postgresql_version must be a non-empty exact release")
        target_match = lambda item: item.get("postgresql_version") == pg_version
    platform = selection["platform"]
    if not isinstance(platform, str) or platform not in RUNNERS:
        raise ValueError(f"selected target must be a declared platform with a standard runner: {platform}")
    architecture = platform.split("-", 1)[1]

    queue = extension_work_queue.build_queue(root)
    matches = [item for item in queue["work_items"]
               if item.get("kind") == "build-extension"
               and all(item.get(key) == selection[key] for key in REQUIRED)
               and target_match(item)]
    if len(matches) != 1:
        raise ValueError(f"selection must resolve exactly one declared build-extension group; found {len(matches)}")
    item = matches[0]
    if item.get("blocked_by_unresolved_prerequisite") or any(
            unresolved.get("item_id") == item["id"] for unresolved in queue["unresolved_prerequisites"]):
        raise ValueError(f"selected group has an unresolved prerequisite: {item['id']}")
    if item.get("platform") != platform or item.get("verification_status") not in {"unverified", "complete"}:
        raise ValueError("selected target is inconsistent with the declared platform group")
    closure = extension_work_queue.select_item_closure(queue, item["id"], 8)
    if closure[-1]["id"] != item["id"]:
        raise ValueError("selected group is not the final item in its dependency closure")
    return {
        "project": item["project"],
        "version": item["version"],
        "platform": item["platform"],
        "postgresql_major": item["postgresql_major"],
        "architecture": architecture,
        "runner": RUNNERS[platform],
        "group_id": item["id"],
        "closure_ids": [entry["id"] for entry in closure],
        "postgresql_version": item["postgresql_version"],
        "verification_status": item["verification_status"],
        # Retain the historical pilot workflow's output names while it is in use.
        "build_postgresql_version": item["postgresql_version"],
        "range_from": item["postgresql_version"],
        "range_to": item["postgresql_version"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Resolve one declared extension build target against the work queue.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--selection", type=Path, help="checked-in JSON target selection")
    parser.add_argument("--project", help="extension project name")
    parser.add_argument("--version", help="extension version")
    parser.add_argument("--platform", help="declared target platform, such as macos-arm64")
    parser.add_argument("--postgresql-major", type=int, help="PostgreSQL major version")
    parser.add_argument("--postgresql-version", help="exact selected PostgreSQL release, such as 17.11")
    parser.add_argument("--github-output", type=Path, help="append resolved values to a GitHub Actions output file")
    args = parser.parse_args(argv)
    direct_values = (args.project, args.version, args.platform, args.postgresql_major,
                     args.postgresql_version)
    if args.selection is not None:
        if any(value is not None for value in direct_values):
            parser.error("--selection cannot be combined with direct target options")
    elif (any(value is None for value in (args.project, args.version, args.platform))
          or (args.postgresql_major is None) == (args.postgresql_version is None)):
        parser.error("provide --selection or project, version, platform, and exactly one PostgreSQL major or exact version")
    try:
        selection = (json.loads(args.selection.read_text()) if args.selection is not None else {
            "project": args.project,
            "version": args.version,
            "platform": args.platform,
            **({"postgresql_major": args.postgresql_major} if args.postgresql_major is not None
               else {"postgresql_version": args.postgresql_version}),
        })
        result = resolve(args.root, selection)
        print(json.dumps(result, indent=2, sort_keys=True))
        if args.github_output:
            with args.github_output.open("a") as output:
                for key, value in result.items():
                    output.write(f"{key}={json.dumps(value, separators=(',', ':')) if isinstance(value, (dict, list)) else value}\n")
        return 0
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"select-extension-work: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
