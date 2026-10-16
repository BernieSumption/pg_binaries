#!/usr/bin/env python3
"""Write schema-v2 verification records for successful macOS pilot archives."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform as host_platform
import re
import sys

import coverage


DEPENDENCY_PROFILE = "macho-system-dependencies-v1"
HASH_CHUNK_SIZE = 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def emit(root, archive_dir, output_dir, pg_version, revision, os_version,
         architecture, image_id):
    if architecture not in {"x86_64", "arm64"}:
        raise coverage.CoverageError("macOS pilot runner architecture must be x86_64 or arm64")
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", revision):
        raise coverage.CoverageError("test revision must be a full Git commit hash")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version):
        raise coverage.CoverageError("macOS version must be numeric dotted version")
    if not image_id:
        raise coverage.CoverageError("runner image identifier is required")
    profile_id = f"macos-pilot-{architecture}"
    platform = f"macos-{architecture}"
    profile = coverage.verification_profile(root, profile_id)
    if profile["scope"] != "pilot-smoke" or platform not in profile["platforms"]:
        raise coverage.CoverageError("registered profile is not the expected macOS pilot")
    support = coverage.load_json(Path(root) / "support.json")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "")
    if not run_id or not repository or not server_url:
        raise coverage.CoverageError("GitHub Actions run provenance is required")
    names = (
        (f"postgresql-{pg_version}-macos-{architecture}.tar.gz", "postgresql", pg_version),
        (f"pgvector-0.8.7-postgresql-{pg_version}-macos-{architecture}.tar.gz", "vector", "0.8.7"),
    )
    records = []
    for filename, component, version in names:
        archive = archive_dir / filename
        checksum_path = archive_dir / f"{filename}.sha256"
        try:
            checksum_fields = checksum_path.read_text(encoding="utf-8").split()
            expected_sha = checksum_fields[0]
        except (OSError, IndexError) as exc:
            raise coverage.CoverageError(f"missing checksum for {filename}") from exc
        if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha):
            raise coverage.CoverageError(f"malformed checksum for {filename}")
        actual_sha = sha256_file(archive)
        if actual_sha.lower() != expected_sha.lower():
            raise coverage.CoverageError(f"archive checksum does not match {filename}")
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
            "sha256": actual_sha,
            "component": component,
            "version": version,
            "platform": platform,
            "postgresql_version": pg_version,
            "environment": {
                "os": "macos",
                "os_version": os_version,
                "architecture": architecture,
                "clean_system": True,
                "endpoint": "current",
                "image_id": image_id,
                "dependency_check_profile": DEPENDENCY_PROFILE,
                "dependency_checks_passed": True,
            },
        }
        coverage.validate_verification_record(record, support, root)
        path = output_dir / f"{component}-{pg_version}-macos-{architecture}-{run_id}.json"
        records.append((path, record))
    output_dir.mkdir(parents=True, exist_ok=True)
    for path, record in records:
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [path for path, _ in records]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--architecture", default=host_platform.machine())
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args()
    try:
        paths = emit(args.root, args.archives, args.output, args.postgresql_version,
                     os.environ.get("GITHUB_SHA", ""), args.os_version,
                     args.architecture, args.image_id)
        for path in paths:
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError) as exc:
        print(f"pilot record: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
