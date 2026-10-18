#!/usr/bin/env python3
"""Load and validate the shared Windows PostgreSQL core identity pin."""

import argparse
import json
from pathlib import Path
import re
import sys


PIN_PATH = Path(__file__).resolve().parents[1] / "support/windows-core-pins/18.6-x86_64.json"
PG_VERSIONS = ("15.19", "16.15", "17.11", "18.6")
REQUIRED = {
    "schema_version", "postgresql_version", "platform", "architecture", "artifact_name",
    "archive_name", "run_id", "build_id", "source_revision", "sha256", "profile_id", "status",
}


def load_identity(path=None, pg_version="18.6"):
    if pg_version not in PG_VERSIONS:
        raise ValueError("unsupported Windows PostgreSQL target")
    path = PIN_PATH.parent / f"{pg_version}-x86_64.json" if path is None else path
    try:
        identity = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Windows core identity pin is missing or invalid: {path}") from exc
    if not isinstance(identity, dict) or set(identity) != REQUIRED:
        raise ValueError("Windows core identity pin has missing or unexpected fields")
    if (identity["schema_version"] != 1 or identity["postgresql_version"] != pg_version
            or identity["platform"] != "windows-x86_64" or identity["architecture"] != "x86_64"
            or identity["artifact_name"] != f"windows-postgresql-{pg_version}-pilot"
            or identity["archive_name"] != f"postgresql-{pg_version}-windows-x86_64.tar.gz"
            or identity["profile_id"] != "windows-publication-current-x86_64"
            or identity["status"] != "current-profile-core-redistribution-pending"
            or not re.fullmatch(r"[1-9][0-9]*", str(identity["run_id"]))
            or not re.fullmatch(rf"github-{identity['run_id']}-[1-9][0-9]*", str(identity["build_id"]))
            or not re.fullmatch(r"[0-9a-f]{40}", str(identity["source_revision"]))
            or not re.fullmatch(r"[0-9a-f]{64}", str(identity["sha256"]))):
        raise ValueError(f"Windows core identity pin does not match the expected {pg_version} x86-64 shape")
    return identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgresql-version", choices=PG_VERSIONS, default="18.6")
    parser.add_argument("--path", type=Path)
    parser.add_argument("--field", choices=sorted(REQUIRED))
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()
    identity = load_identity(path=args.path, pg_version=args.postgresql_version)
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
