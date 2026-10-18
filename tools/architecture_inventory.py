#!/usr/bin/env python3
"""Inventory workflow entry points and their registered verification profiles."""

import argparse
import json
from pathlib import Path
import re
import sys


RUN_ID = re.compile(r"(?m)^\s*run-id:\s*([0-9]+)\s*$")
PUSH = re.compile(r"(?m)^  push:\s*$")
WORKFLOW_CALL = re.compile(r"(?m)^  workflow_call:\s*$")


def category(name):
    if name.endswith("-publication.yml"):
        return "publication"
    if name in {"support-coverage.yml", "profile-change-scope.yml"}:
        return "infrastructure"
    if any(term in name for term in ("pilot", "feasibility", "probe", "qemu", "trial")):
        return "investigation"
    return "review"


def inventory(root):
    root = Path(root)
    registry = json.loads((root / "support/verification-profiles.json").read_text(encoding="utf-8"))
    profiles_by_workflow = {}
    for profile_id, profile in registry["profiles"].items():
        for source in profile.get("sources", []):
            path = source.split("#", 1)[0]
            if path.startswith(".github/workflows/"):
                profiles_by_workflow.setdefault(path, set()).add(profile_id)
    rows = []
    for path in sorted((root / ".github/workflows").glob("*.y*ml")):
        relative = path.relative_to(root).as_posix()
        contents = path.read_text(encoding="utf-8")
        rows.append({
            "path": relative,
            "category": category(path.name),
            "profiles": sorted(profiles_by_workflow.get(relative, ())),
            "push_trigger": bool(PUSH.search(contents)),
            "workflow_call": bool(WORKFLOW_CALL.search(contents)),
            "fixed_run_ids": RUN_ID.findall(contents),
        })
    return {"schema_version": 1, "workflows": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = inventory(args.root)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"architecture inventory: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
