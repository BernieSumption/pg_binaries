#!/usr/bin/env python3
"""Select changed pg_jsonschema macOS publication targets from profile revisions."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coverage = _load_module("profile_coverage", "coverage.py")
target_loader = _load_module("pg_jsonschema_macos_target", "pg_jsonschema_macos_target.py")


def changed_targets(before_root, current_root, targets_dir=None):
    """Return sorted matrix entries whose current verification profile changed."""
    current_root = Path(current_root)
    targets_dir = Path(targets_dir) if targets_dir else current_root / "tools" / "pg_jsonschema_macos_targets"
    targets = []
    declared_profiles = set()
    for path in sorted(targets_dir.glob("*.json")):
        target = target_loader.load_target(path)
        if target.profile_id in declared_profiles:
            raise ValueError(f"duplicate pg_jsonschema macOS target profile: {target.profile_id}")
        declared_profiles.add(target.profile_id)
        current = coverage.verification_profile(current_root, target.profile_id)
        if (current["scope"] != "publication" or current["platforms"] != [target.platform]
                or current["case_ids"] != ["archive-suite", "static-analysis"]):
            raise ValueError(f"target {path.name} does not match its verification profile declaration")
        selected = before_root is None
        if before_root is not None:
            try:
                before = coverage.verification_profile(before_root, target.profile_id)
            except Exception as exc:
                print(f"Cannot resolve base profile {target.profile_id!r}; selecting it: {exc}",
                      file=sys.stderr)
                selected = True
            else:
                selected = before["profile_revision"] != current["profile_revision"]
        if selected:
            targets.append({"postgresql_version": target.postgresql_version,
                            "extension_version": target.extension_version,
                            "architecture": target.architecture})
    registry = coverage.load_json(current_root / "support" / "verification-profiles.json")
    registered_profiles = {name for name in registry["profiles"]
                           if name.startswith("pg-jsonschema-publication-macos-")}
    if declared_profiles != registered_profiles:
        raise ValueError("pg_jsonschema macOS targets and publication profiles differ")
    return sorted(targets, key=lambda item: (item["postgresql_version"], item["architecture"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-root", type=Path)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--targets-dir", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        before_root = args.before_root if args.before_root and args.before_root.exists() else None
        selected = changed_targets(before_root, args.current_root, args.targets_dir)
    except Exception as exc:
        parser.exit(2, f"pg_jsonschema macOS profile selection failed: {exc}\n")
    rendered = json.dumps(selected, separators=(",", ":"))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"targets={rendered}\n")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
