#!/usr/bin/env python3
"""Select changed HypoPG publication profiles from the verification registry."""

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

_COVERAGE_SPEC = importlib.util.spec_from_file_location(
    "profile_coverage", Path(__file__).with_name("coverage.py"))
coverage = importlib.util.module_from_spec(_COVERAGE_SPEC)
_COVERAGE_SPEC.loader.exec_module(coverage)


def changed_targets(before_root, current_root, profile_prefix):
    """Return sorted target suffixes whose current profile revision changed."""
    current_root = Path(current_root)
    registry = coverage.load_json(current_root / "support" / "verification-profiles.json")
    profiles = registry.get("profiles") if isinstance(registry, dict) else None
    if not isinstance(profiles, dict):
        raise ValueError("verification profile registry has no profiles object")

    targets = []
    for profile_id in sorted(profiles):
        if not profile_id.startswith(profile_prefix):
            continue
        target = profile_id[len(profile_prefix):]
        if not re.fullmatch(r"[0-9]+\.[0-9]+", target):
            raise ValueError(f"verification profile {profile_id!r} has no exact PostgreSQL release suffix")
        current = coverage.verification_profile(current_root, profile_id)
        if before_root is None:
            targets.append(target)
            continue
        try:
            before = coverage.verification_profile(before_root, profile_id)
        except Exception as exc:
            print(f"Cannot resolve base profile {profile_id!r}; selecting it fail-open: {exc}",
                  file=sys.stderr)
            targets.append(target)
        else:
            if before["profile_revision"] != current["profile_revision"]:
                targets.append(target)
    return targets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-root", type=Path)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--profile-prefix", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        before_root = args.before_root if args.before_root and args.before_root.exists() else None
        targets = changed_targets(before_root, args.current_root, args.profile_prefix)
    except Exception as exc:
        parser.exit(2, f"HypoPG profile selection failed: {exc}\n")
    rendered = json.dumps(targets, separators=(",", ":"))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"targets={rendered}\n")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
