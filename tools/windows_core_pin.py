#!/usr/bin/env python3
"""Load and validate the shared Windows PostgreSQL 18.6 core identity pin."""

import argparse
import json
from pathlib import Path
import re
import sys


PIN_PATH = Path(__file__).resolve().parents[1] / "support/windows-core-pins/18.6-x86_64.json"
REQUIRED = {
    "schema_version", "postgresql_version", "platform", "architecture", "artifact_name",
    "archive_name", "run_id", "build_id", "source_revision", "sha256", "profile_id", "status",
}


def load_identity(path=PIN_PATH):
    try:
        identity = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Windows core identity pin is missing or invalid: {path}") from exc
    if not isinstance(identity, dict) or set(identity) != REQUIRED:
        raise ValueError("Windows core identity pin has missing or unexpected fields")
    if (identity["schema_version"] != 1 or identity["postgresql_version"] != "18.6"
            or identity["platform"] != "windows-x86_64" or identity["architecture"] != "x86_64"
            or identity["artifact_name"] != "windows-postgresql-18.6-pilot"
            or identity["archive_name"] != "postgresql-18.6-windows-x86_64.tar.gz"
            or identity["profile_id"] != "windows-publication-current-x86_64"
            or identity["status"] != "current-profile-core-redistribution-pending"
            or not re.fullmatch(r"[1-9][0-9]*", str(identity["run_id"]))
            or identity["build_id"] != f"github-{identity['run_id']}-1"
            or not re.fullmatch(r"[0-9a-f]{40}", str(identity["source_revision"]))
            or not re.fullmatch(r"[0-9a-f]{64}", str(identity["sha256"]))):
        raise ValueError("Windows core identity pin does not match the expected 18.6 x86-64 shape")
    return identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--field", choices=sorted(REQUIRED))
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()
    identity = load_identity()
    if args.github_output:
        for key in ("run_id", "artifact_name", "archive_name", "sha256", "build_id", "source_revision"):
            print(f"{key}={identity[key]}")
    elif args.field:
        print(identity[args.field])
    else:
        print(json.dumps(identity, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
