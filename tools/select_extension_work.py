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


RUNNERS = {"x86_64": "ubuntu-24.04", "arm64": "ubuntu-24.04-arm"}
REQUIRED = {"project", "version", "platform", "postgresql_major"}


def resolve(root, selection):
    if not isinstance(selection, dict) or set(selection) != REQUIRED:
        raise ValueError("selection must contain exactly project, version, platform, and postgresql_major")
    if not isinstance(selection["postgresql_major"], int) or isinstance(selection["postgresql_major"], bool):
        raise ValueError("postgresql_major must be an integer")
    platform = selection["platform"]
    if not isinstance(platform, str) or not platform.startswith("linux-"):
        raise ValueError("selected target must be a declared Linux platform")
    architecture = platform.removeprefix("linux-")
    if architecture not in RUNNERS:
        raise ValueError(f"no standard Linux runner mapping for architecture: {architecture}")

    queue = extension_work_queue.build_queue(root)
    matches = [item for item in queue["work_items"]
               if item.get("kind") == "build-extension"
               and all(item.get(key) == selection[key] for key in REQUIRED)]
    if len(matches) != 1:
        raise ValueError(f"selection must resolve exactly one declared build-extension group; found {len(matches)}")
    item = matches[0]
    if item.get("blocked_by_unresolved_prerequisite") or any(
            unresolved.get("item_id") == item["id"] for unresolved in queue["unresolved_prerequisites"]):
        raise ValueError(f"selected group has an unresolved prerequisite: {item['id']}")
    if item.get("platform") != platform or item.get("range_status") not in {"unverified", "complete"}:
        raise ValueError("selected target is inconsistent with the declared Linux group")
    closure = extension_work_queue.select_item_closure(queue, item["id"], 8)
    if closure[-1]["id"] != item["id"]:
        raise ValueError("selected group is not the final item in its dependency closure")
    return {
        "project": item["project"],
        "version": item["version"],
        "platform": item["platform"],
        "postgresql_major": item["postgresql_major"],
        "architecture": architecture,
        "runner": RUNNERS[architecture],
        "group_id": item["id"],
        "closure_ids": [entry["id"] for entry in closure],
        "build_postgresql_version": item["build_postgresql_version"],
        "candidate_range": item["postgresql_range"],
        "range_status": "unverified",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--selection", type=Path, required=True, help="checked-in JSON target selection")
    parser.add_argument("--github-output", type=Path, help="append resolved values to a GitHub Actions output file")
    args = parser.parse_args(argv)
    try:
        result = resolve(args.root, json.loads(args.selection.read_text()))
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
