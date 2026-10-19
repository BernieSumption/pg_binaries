#!/usr/bin/env python3
"""Validate and retain compact pgTAP Linux publication evidence."""

import argparse
from pathlib import Path
import sys

import coverage
from import_linux_single_extension_publication import ARCHITECTURES, MAX_EVIDENCE_BYTES, import_run as _import_run


def import_run(root, core_artifact, pgtap_artifact, run_id, architecture, postgresql_version="18.6"):
    return _import_run(
        root, core_artifact, pgtap_artifact, run_id, architecture, postgresql_version,
        slug="pgtap", project="pgtap", version="1.3.4",
        profile_prefix="pgtap", publication_dir="pgtap-publication",
        extension_dir_name="pgtap", report_name="pgtap.json",
        extension_dir_fallback=True, target_profile=True, target_version_dir=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True)
    parser.add_argument("--pgtap-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    parser.add_argument("--postgresql-version", default="18.6")
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact, args.pgtap_artifact,
                                   args.run_id, args.architecture, args.postgresql_version)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux pgTAP publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
