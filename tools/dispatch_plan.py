#!/usr/bin/env python3
"""Validate one declared extension request and return its queue dependency plan."""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    "dispatch_plan_extension_queue", Path(__file__).with_name("extension_work_queue.py"))
extension_work_queue = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extension_work_queue)

RUNNERS = {
    "linux-x86_64": "ubuntu-24.04",
    "linux-arm64": "ubuntu-24.04-arm",
    "macos-x86_64": "macos-15-intel",
    "macos-arm64": "macos-15",
    "windows-x86_64": "windows-2022",
}
REQUIRED = {"project", "version", "postgresql_version", "platform"}


def resolve(root, request, candidate_manifest=None, expected_build_inputs=None):
    """Resolve an exact request to all queue tasks needed to build and verify it."""
    if (not isinstance(request, dict) or not REQUIRED <= set(request)
            or set(request) - (REQUIRED | {"retry"})):
        raise ValueError("request must contain project, version, postgresql_version, platform, and optional retry")
    for field in REQUIRED:
        if not isinstance(request[field], str) or not request[field]:
            raise ValueError(f"{field} must be a non-empty string")
    if not re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", request["postgresql_version"]):
        raise ValueError("postgresql_version must be an exact numeric release")
    retry = request.get("retry", False)
    if not isinstance(retry, bool):
        raise ValueError("retry must be a boolean")
    platform = request["platform"]
    if platform not in RUNNERS:
        raise ValueError(f"undeclared platform: {platform}")

    queue = extension_work_queue.build_queue(root, candidate_manifest, expected_build_inputs)
    target = {key: request[key] for key in REQUIRED}
    groups = [item for item in queue["work_items"]
              if item.get("kind") == "build-extension"
              and item.get("project") == target["project"]
              and item.get("version") == target["version"]
              and item.get("platform") == platform
              and item.get("postgresql_version") == target["postgresql_version"]]
    if len(groups) != 1:
        raise ValueError(f"request must resolve exactly one declared target; found {len(groups)}")
    group = groups[0]
    matching_verifications = [item for item in queue["work_items"]
                              if item.get("kind") == "verify-extension"
                              and item.get("project") == target["project"]
                              and item.get("version") == target["version"]
                              and item.get("platform") == platform
                              and item.get("postgresql_version") == target["postgresql_version"]]
    if not matching_verifications:
        raise ValueError("declared target has no verification work")

    included = {}
    for item in matching_verifications:
        for dependency in extension_work_queue.select_item_closure(queue, item["id"], 128):
            included[dependency["id"]] = dependency
    pending = set(included)
    ordered = []
    selected = set()
    while pending:
        ready = sorted(item_id for item_id in pending
                       if set(included[item_id].get("depends_on", [])) <= selected)
        if not ready:
            raise ValueError("selected dependency closure contains a cycle or missing dependency")
        item_id = ready[0]
        ordered.append(included[item_id])
        selected.add(item_id)
        pending.remove(item_id)
    should_dispatch = retry or any(item.get("status") != "complete" for item in ordered)
    return {
        "schema_version": 1,
        "target": {**target, "postgresql_major": group["postgresql_major"]},
        "retry": retry,
        "should_dispatch": should_dispatch,
        "runner": RUNNERS[platform],
        "work_items": ordered,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--request", type=Path, required=True, help="one-target request JSON")
    parser.add_argument("--candidate-manifest", type=Path,
                        help="retrieved unpublished Actions archives eligible for reuse")
    parser.add_argument("--expected-build-inputs", type=Path,
                        help="current build-input identities for exact candidate targets")
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        expected_inputs = (extension_work_queue.load_expected_build_inputs(args.expected_build_inputs)
                           if args.expected_build_inputs else None)
        print(json.dumps(resolve(args.root, request, args.candidate_manifest, expected_inputs),
                         indent=2, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"dispatch-plan: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
