#!/usr/bin/env python3
"""Select changed declared macOS arm64 HypoPG publication profiles."""

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

_PROFILE = re.compile(r"^hypopg-publication-macos-arm64-(17\.11|18\.6)$")


def changed_targets(before_root, current_root):
    """Return exact PostgreSQL releases whose declared profile revision changed."""
    registry = coverage.load_json(Path(current_root) / "support" / "verification-profiles.json")
    profiles = registry.get("profiles") if isinstance(registry, dict) else None
    if not isinstance(profiles, dict):
        raise ValueError("verification profile registry has no profiles object")
    targets = []
    for profile_id in sorted(profiles):
        match = _PROFILE.fullmatch(profile_id)
        if not match:
            continue
        current = coverage.verification_profile(current_root, profile_id)
        try:
            before = coverage.verification_profile(before_root, profile_id)
        except Exception as exc:
            print(f"Cannot resolve base profile {profile_id!r}; selecting it fail-open: {exc}",
                  file=sys.stderr)
            targets.append(match.group(1))
            continue
        if before["profile_revision"] != current["profile_revision"]:
            targets.append(match.group(1))
    return targets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-root", type=Path, required=True)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        targets = changed_targets(args.before_root, args.current_root)
    except Exception as exc:
        parser.exit(2, f"HypoPG macOS arm64 profile selection failed: {exc}\n")
    rendered = json.dumps(targets, separators=(",", ":"))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"targets={rendered}\n")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
