#!/usr/bin/env python3
"""Generate a static Windows PostgreSQL core target from current support selection."""

import argparse
import json
from pathlib import Path
import sys

import coverage


ROOT = Path(__file__).resolve().parents[1]
TARGET_FIELDS = {
    "schema_version", "postgresql_version", "platform", "architecture",
    "archive_name", "profile_id", "status",
}
PROFILE_ID = "windows-publication-current-x86_64"
STATUS = "current-profile-core-redistribution-pending"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def target_for(postgresql_version, root=ROOT):
    root = Path(root)
    support = coverage.load_json(root / "support.json")
    releases = coverage.release_snapshot(
        coverage.load_json(root / "support/postgresql-releases.json"), support)
    core, _ = coverage.expected_targets(support, releases)
    if (postgresql_version, "windows-x86_64") not in core:
        raise ValueError(f"PostgreSQL {postgresql_version} windows-x86_64 is not selected")
    return {
        "schema_version": 1,
        "postgresql_version": postgresql_version,
        "platform": "windows-x86_64",
        "architecture": "x86_64",
        "archive_name": f"postgresql-{postgresql_version}-windows-x86_64.tar.gz",
        "profile_id": PROFILE_ID,
        "status": STATUS,
    }


def load_target(path, postgresql_version=None, root=ROOT, allow_identity_template=False):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read Windows core target: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Windows core target must be an object")
    if allow_identity_template:
        expected = TARGET_FIELDS | {
            "artifact_name", "run_id", "build_id", "source_revision", "sha256",
        }
        if set(value) == expected:
            value = {key: value[key] for key in TARGET_FIELDS}
    if set(value) != TARGET_FIELDS:
        raise ValueError("Windows core target has missing or unexpected fields")
    version = value.get("postgresql_version")
    if postgresql_version is not None and version != postgresql_version:
        raise ValueError("Windows core target PostgreSQL version does not match request")
    expected = target_for(version, root)
    if value != expected:
        raise ValueError("Windows core target does not match current support selection")
    return expected


def write_target(postgresql_version, output, root=ROOT):
    value = target_for(postgresql_version, root)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        write_target(args.postgresql_version, args.output)
        print(f"Wrote static Windows PostgreSQL core target: {args.output}")
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Windows core target: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
