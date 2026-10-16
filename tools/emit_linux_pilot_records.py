#!/usr/bin/env python3
"""Write schema-v2 verification records for successful Linux pilot archives."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform as host_platform
import re
import sys

import coverage


PILOTS = {
    "x86_64": "linux-pilot-x86_64",
    "arm64": "linux-pilot-arm64",
}
DEPENDENCY_PROFILE = "linux-runtime-v1"
HASH_CHUNK_SIZE = 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def os_release(path=Path("/etc/os-release")):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    return values


def emit(root, archive_dir, output_dir, pg_version, architecture, revision,
         image_id, release, machine, kernel_version):
    if architecture not in PILOTS:
        raise coverage.CoverageError("architecture must be x86_64 or arm64")
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", revision):
        raise coverage.CoverageError("test revision must be a full Git commit hash")
    if not image_id.startswith("sha256:") or len(image_id) != 71:
        raise coverage.CoverageError("verifier image ID must be a concrete sha256 image ID")
    expected_machine = {"x86_64": "x86_64", "arm64": "aarch64"}[architecture]
    if machine != expected_machine:
        raise coverage.CoverageError(f"runner architecture {machine!r} does not match {architecture}")
    kernel_match = re.match(r"^(\d+(?:\.\d+)*)", kernel_version)
    if not kernel_match:
        raise coverage.CoverageError("runner kernel version must start with a numeric version")
    os_version = kernel_match.group(1)
    distro_version, pretty_name = release.get("VERSION_ID"), release.get("PRETTY_NAME")
    if not isinstance(distro_version, str) or not re.fullmatch(r"\d+(?:\.\d+)*", distro_version):
        raise coverage.CoverageError("runner OS release must contain a numeric VERSION_ID")
    if not isinstance(pretty_name, str) or not pretty_name:
        raise coverage.CoverageError("runner OS release must contain PRETTY_NAME")
    profile = coverage.verification_profile(root, PILOTS[architecture])
    if profile["scope"] != "pilot-smoke" or f"linux-{architecture}" not in profile["platforms"]:
        raise coverage.CoverageError("registered profile is not the expected Linux pilot")
    support = coverage.load_json(Path(root) / "support.json")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not run_id or not os.environ.get("GITHUB_REPOSITORY") or not os.environ.get("GITHUB_SERVER_URL"):
        raise coverage.CoverageError("GitHub Actions run provenance is required")
    names = (
        (f"postgresql-{pg_version}-linux-{architecture}.tar.gz", "postgresql", pg_version),
        (f"pgvector-0.8.7-postgresql-{pg_version}-linux-{architecture}.tar.gz", "vector", "0.8.7"),
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
            "test_revision": revision,
            "ci": {
                "provider": "github-actions",
                "run_id": run_id,
                "run_url": (os.environ.get("GITHUB_SERVER_URL", "") + "/" +
                            os.environ.get("GITHUB_REPOSITORY", "") + "/actions/runs/" +
                            run_id),
                "source_revision": revision,
                "build_revision": revision,
                "test_revision": revision,
            },
            "outcome": "passed",
            "sha256": actual_sha,
            "component": component,
            "version": version,
            "platform": f"linux-{architecture}",
            "postgresql_version": pg_version,
            "environment": {
                "os": "linux",
                "os_version": os_version,
                "kernel_release": kernel_version,
                "distribution": pretty_name,
                "distribution_version": distro_version,
                "architecture": architecture,
                "clean_system": True,
                "endpoint": "current",
                "image_id": image_id,
                "dependency_check_profile": DEPENDENCY_PROFILE,
                "dependency_checks_passed": True,
            },
        }
        coverage.validate_verification_record(record, support, root)
        path = output_dir / f"{component}-{pg_version}-linux-{architecture}-{run_id}.json"
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
    parser.add_argument("--architecture", choices=sorted(PILOTS), required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--kernel-version", required=True)
    args = parser.parse_args()
    try:
        release = os_release()
        paths = emit(args.root, args.archives, args.output, args.postgresql_version,
                     args.architecture, os.environ.get("GITHUB_SHA", ""), args.image_id,
                     release, host_platform.machine(), args.kernel_version)
        for path in paths:
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError) as exc:
        print(f"pilot record: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
