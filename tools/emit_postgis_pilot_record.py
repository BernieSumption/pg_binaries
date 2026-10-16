#!/usr/bin/env python3
"""Record the checks passed by a PostGIS Linux pilot archive."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys

import coverage


PROFILE_ID = "postgis-pilot-linux-x86_64"
ARCHIVE = "postgis-3.6.4-postgresql-18.6-linux-x86_64.tar.gz"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def emit(root, archives, core_archives, output, image_id, kernel):
    if platform.machine() != "x86_64":
        raise coverage.CoverageError("PostGIS pilot requires an x86-64 runner")
    revision = os.environ.get("GITHUB_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", revision) or not all((
        run_id, repository, server_url
    )):
        raise coverage.CoverageError("GitHub Actions revision and run provenance are required")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise coverage.CoverageError("verifier image ID must be a concrete SHA-256")
    kernel_match = re.match(r"^(\d+(?:\.\d+)*)", kernel)
    if not kernel_match:
        raise coverage.CoverageError("runner kernel must start with a numeric version")
    release = {}
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            release[key] = value.strip().strip('"')
    if not release.get("PRETTY_NAME") or not re.fullmatch(r"\d+(?:\.\d+)*", release.get("VERSION_ID", "")):
        raise coverage.CoverageError("runner OS release is incomplete")

    profile = coverage.verification_profile(root, PROFILE_ID)
    if profile["scope"] != "pilot-smoke" or "linux-x86_64" not in profile["platforms"]:
        raise coverage.CoverageError("invalid PostGIS pilot profile")
    archive = archives / ARCHIVE
    checksum = archives / f"{ARCHIVE}.sha256"
    fields = checksum.read_text(encoding="utf-8").split()
    if len(fields) != 2 or fields[1] != ARCHIVE:
        raise coverage.CoverageError("PostGIS archive checksum file is malformed")
    digest = sha256_file(archive)
    if digest.lower() != fields[0].lower():
        raise coverage.CoverageError("PostGIS archive checksum mismatch")
    core_name = "postgresql-18.6-linux-x86_64.tar.gz"
    core_fields = (core_archives / f"{core_name}.sha256").read_text(encoding="utf-8").split()
    if len(core_fields) != 2 or core_fields[1] != core_name:
        raise coverage.CoverageError("PostgreSQL core checksum file is malformed")
    core_digest = sha256_file(core_archives / core_name)
    if core_digest.lower() != core_fields[0].lower():
        raise coverage.CoverageError("PostgreSQL core archive checksum mismatch")
    record = {
        "schema_version": 2,
        "scope": "pilot-smoke",
        "profile_id": profile["profile_id"],
        "profile_revision": profile["profile_revision"],
        "test_cases": profile["case_ids"],
        "verification_profile": profile,
        "test_revision": revision,
        "ci": {
            "provider": "github-actions",
            "run_id": run_id,
            "run_url": f"{server_url}/{repository}/actions/runs/{run_id}",
            "source_revision": revision,
            "build_revision": revision,
            "test_revision": revision,
        },
        "outcome": "passed",
        "sha256": digest,
        "assembled_core": {"archive": core_name, "sha256": core_digest, "version": "18.6"},
        "component": "PostGIS",
        "version": "3.6.4",
        "platform": "linux-x86_64",
        "postgresql_version": "18.6",
        "environment": {
            "os": "linux",
            "os_version": kernel_match.group(1),
            "kernel_release": kernel,
            "distribution": release["PRETTY_NAME"],
            "distribution_version": release["VERSION_ID"],
            "architecture": "x86_64",
            "clean_system": True,
            "endpoint": "current",
            "image_id": image_id,
            "dependency_check_profile": "postgis-runtime-v1",
            "dependency_checks_passed": True,
        },
    }
    support = coverage.load_json(root / "support.json")
    coverage.validate_verification_record(record, support, root)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"postgis-3.6.4-postgresql-18.6-linux-x86_64-{run_id}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--kernel", required=True)
    args = parser.parse_args()
    try:
        print(emit(args.root, args.archives, args.core_archives, args.output,
                   args.image_id, args.kernel))
        return 0
    except (coverage.CoverageError, OSError, ValueError) as exc:
        print(f"PostGIS pilot record: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
