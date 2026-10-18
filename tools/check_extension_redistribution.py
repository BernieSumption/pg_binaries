#!/usr/bin/env python3
"""Check an extension archive's redistribution inventory and evidence files."""

import argparse
import sys

from publication_preflight import PreflightError, _archive_redistribution


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="final extension archive")
    args = parser.parse_args()
    try:
        _archive_redistribution(args.archive, metadata_sibling=True)
    except (OSError, PreflightError) as exc:
        parser.error(str(exc))
    print(f"PASS: redistribution inventory and evidence in {args.archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
