#!/usr/bin/env python3
"""Decide whether a platform workflow must run for a profile change."""

import argparse
from pathlib import Path
import sys

import coverage


def should_run(before_root, current_root, profile_id):
    current = coverage.verification_profile(current_root, profile_id)
    try:
        before = coverage.verification_profile(before_root, profile_id)
    except Exception as exc:
        print(f"Cannot resolve base profile {profile_id!r}; running fail-open: {exc}",
              file=sys.stderr)
        return True
    return before["profile_revision"] != current["profile_revision"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-root", type=Path, required=True)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--profile-id", required=True)
    args = parser.parse_args(argv)
    try:
        run = should_run(args.before_root, args.current_root, args.profile_id)
    except Exception as exc:
        print(f"Cannot resolve current profile {args.profile_id!r}: {exc}", file=sys.stderr)
        return 2
    print(f"should_run={'true' if run else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
