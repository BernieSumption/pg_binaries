#!/usr/bin/env python3
"""Write schema-v2 records for Linux kernel 5.15 QEMU archive verification."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import coverage


ARCHITECTURES = {
    "x86_64": {
        "profile": "linux-minimum-kernel-x86_64",
        "image_sha256": "e3297e0aa6c408ac90d854348465d3991c65159b444c4ef9016f52f6807290e3",
        "script": "scripts/linux/qemu-kernel-515-smoke.sh",
    },
    "arm64": {
        "profile": "linux-minimum-kernel-arm64",
        "image_sha256": "86e13258765945ad792dac75fac7f02f4db9fa73a4a535ffa472266e7041fa19",
        "script": "scripts/qemu/arm64-515-smoke.sh",
    },
}
HASH_CHUNK_SIZE = 1024 * 1024
DEPENDENCY_PROFILE = "linux-runtime-v1"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def parse_key_values(path):
    values = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise coverage.CoverageError(f"cannot read {path.name}: {exc}") from exc
    for line in lines:
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def parse_archive_checksums(path):
    checksums = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise coverage.CoverageError(f"cannot read archive-checksums.sha256: {exc}") from exc
    for line in lines:
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+)", line)
        if not match:
            raise coverage.CoverageError("archive-checksums.sha256 contains a malformed line")
        name = Path(match.group(2)).name
        if name in checksums:
            raise coverage.CoverageError(f"duplicate archive checksum for {name}")
        checksums[name] = match.group(1).lower()
    return checksums


def emit(root, archives, evidence, output, pg_version, architecture, revision,
         outcome="passed"):
    if architecture not in ARCHITECTURES:
        raise coverage.CoverageError("architecture must be x86_64 or arm64")
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", revision):
        raise coverage.CoverageError("test revision must be a full Git commit hash")
    if not re.fullmatch(r"(?:15|16|17|18)\.\d+", pg_version):
        raise coverage.CoverageError("unsupported PostgreSQL pilot version")
    if outcome not in {"passed", "failed", "skipped"}:
        raise coverage.CoverageError("outcome must be passed, failed, or skipped")

    arch = ARCHITECTURES[architecture]
    script = (Path(root) / arch["script"]).read_text(encoding="utf-8")
    if not re.search(rf"(?m)^image_sha256={arch['image_sha256']}$", script):
        raise coverage.CoverageError("pinned guest image hash does not match QEMU script")
    kernel_release = None
    guest_distribution = "Ubuntu 22.04"
    if outcome == "passed":
        if evidence is None:
            raise coverage.CoverageError("passed outcome requires QEMU evidence")
        env = parse_key_values(evidence / "environment.txt")
        if env.get("postgresql_version") != pg_version:
            raise coverage.CoverageError("QEMU evidence PostgreSQL version does not match request")
        if env.get("test_revision", "").lower() != revision.lower():
            raise coverage.CoverageError("QEMU evidence revision does not match GitHub revision")
        if env.get("image_sha256", "").lower() != arch["image_sha256"]:
            raise coverage.CoverageError("QEMU evidence does not identify the pinned guest image")
        log = (evidence / "full-verifier.log").read_text(encoding="utf-8")
        kernel_match = re.search(r"(?m)^guest_kernel=(\S+)$", log)
        if not kernel_match or not kernel_match.group(1).startswith("5.15."):
            raise coverage.CoverageError("full verifier log does not establish a Linux 5.15 guest kernel")
        kernel_release = kernel_match.group(1)
        if not re.search(rf"(?m)^PASS: moved PostgreSQL {re.escape(pg_version)} archive and pgvector 0\.8\.7 archive on Ubuntu ", log):
            raise coverage.CoverageError("full verifier log has no successful archive verification")
        guest_os = re.search(r"(?m)^guest_os=(.+)$", log)
        if not guest_os or "Ubuntu 22.04" not in guest_os.group(1):
            raise coverage.CoverageError("full verifier log does not identify the expected Ubuntu guest")
        guest_distribution = guest_os.group(1)
    names = (
        (f"postgresql-{pg_version}-linux-{architecture}.tar.gz", "postgresql", pg_version),
        (f"pgvector-0.8.7-postgresql-{pg_version}-linux-{architecture}.tar.gz", "vector", "0.8.7"),
    )
    if outcome == "passed":
        checksums = parse_archive_checksums(evidence / "archive-checksums.sha256")
        expected_names = {name for name, _, _ in names}
        if set(checksums) != expected_names:
            raise coverage.CoverageError("archive-checksums.sha256 does not identify exactly the PostgreSQL and pgvector archives")

    profile = coverage.verification_profile(root, arch["profile"])
    if profile["scope"] != "pilot-smoke" or f"linux-{architecture}" not in profile["platforms"]:
        raise coverage.CoverageError("registered profile is not the expected Linux minimum-kernel pilot")
    support = coverage.load_json(Path(root) / "support.json")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "")
    if not run_id or not repository or not server_url:
        raise coverage.CoverageError("GitHub Actions run provenance is required")

    records = []
    for filename, component, version in names:
        archive = Path(archives) / filename
        sidecar = Path(archives) / f"{filename}.sha256"
        try:
            sidecar_fields = sidecar.read_text(encoding="utf-8").split()
        except OSError as exc:
            raise coverage.CoverageError(f"missing checksum sidecar for {filename}") from exc
        if (len(sidecar_fields) != 2
                or not re.fullmatch(r"[0-9a-fA-F]{64}", sidecar_fields[0])
                or Path(sidecar_fields[1].lstrip("*")).name != filename):
            raise coverage.CoverageError(f"malformed checksum sidecar for {filename}")
        sidecar_sha = sidecar_fields[0].lower()
        actual_sha = sha256_file(archive)
        if sidecar_sha != actual_sha or (outcome == "passed" and checksums[filename] != actual_sha):
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
                "run_url": f"{server_url}/{repository}/actions/runs/{run_id}",
                "source_revision": revision,
                "build_revision": revision,
                "test_revision": revision,
            },
            "outcome": outcome,
            "sha256": actual_sha,
            "component": component,
            "version": version,
            "platform": f"linux-{architecture}",
            "postgresql_version": pg_version,
            "environment": {
                "os": "linux",
                "os_version": "5.15",
                **({"kernel_release": kernel_release} if kernel_release else {}),
                "distribution": guest_distribution,
                "distribution_version": "22.04",
                "architecture": architecture,
                "clean_system": outcome == "passed",
                "endpoint": "minimum",
                "image_id": f"sha256:{arch['image_sha256']}",
                "dependency_check_profile": DEPENDENCY_PROFILE,
                "dependency_checks_passed": outcome == "passed",
            },
        }
        coverage.validate_verification_record(record, support, root)
        path = Path(output) / f"{component}-{pg_version}-linux-{architecture}-minimum-{run_id}.json"
        records.append((path, record))
    Path(output).mkdir(parents=True, exist_ok=True)
    for path, record in records:
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [path for path, _ in records]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    parser.add_argument("--outcome", choices=("passed", "failed", "skipped"), default="passed")
    args = parser.parse_args()
    try:
        paths = emit(args.root, args.archives, args.evidence, args.output,
                     args.postgresql_version, args.architecture,
                     os.environ.get("GITHUB_SHA", ""), args.outcome)
        for path in paths:
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError) as exc:
        print(f"minimum-kernel pilot record: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
