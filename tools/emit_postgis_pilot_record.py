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
from emit_linux_minimum_pilot_records import ARCHITECTURES, parse_key_values, parse_archive_checksums


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def emit(root, archives, core_archives, output, image_id, kernel, architecture="x86_64",
         evidence=None, outcome="passed"):
    if outcome not in {"passed", "failed", "skipped"}:
        raise coverage.CoverageError("outcome must be passed, failed, or skipped")
    machines = {"x86_64": "x86_64", "arm64": "aarch64"}
    if architecture not in machines or platform.machine() != machines[architecture]:
        raise coverage.CoverageError("PostGIS pilot requires a matching native runner")
    platform_id = f"linux-{architecture}"
    archive_name = f"postgis-3.6.4-postgresql-18.6-{platform_id}.tar.gz"
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

    endpoint = "current"
    profile_id = f"postgis-pilot-{platform_id}"
    if evidence is not None:
        env = parse_key_values(evidence / "environment.txt")
        pinned = ARCHITECTURES[architecture]["image_sha256"]
        if (env.get("test_revision") != revision or env.get("postgresql_version") != "18.6"
                or env.get("image_sha256") != pinned):
            raise coverage.CoverageError("minimum-kernel evidence provenance mismatch")
        log = (evidence / "full-verifier.log").read_text()
        guest_kernel = re.search(r"(?m)^guest_kernel=(5\.15\.\S+)$", log)
        if (not guest_kernel or "guest_os=Ubuntu 22.04" not in log
                or f"guest_architecture={architecture}\n" not in log):
            raise coverage.CoverageError("minimum-kernel evidence does not establish a clean guest")
        passed_marker = "\nPASS: PostGIS 3.6.4 minimum-kernel archive verification\n" in log
        if outcome == "passed" and not passed_marker:
            raise coverage.CoverageError("minimum-kernel guest verification did not pass")
        kernel = guest_kernel.group(1)
        kernel_match = re.match(r"^(\d+(?:\.\d+)*)", kernel)
        if outcome == "passed":
            release = {"PRETTY_NAME": "Ubuntu 22.04", "VERSION_ID": "22.04"}
        else:
            release = {}
        image_id = f"sha256:{pinned}"
        endpoint = "minimum"
        profile_id = f"postgis-minimum-kernel-{architecture}"
    profile = coverage.verification_profile(root, profile_id)
    if profile["scope"] != "pilot-smoke" or platform_id not in profile["platforms"]:
        raise coverage.CoverageError("invalid PostGIS pilot profile")
    archive = archives / archive_name
    checksum = archives / f"{archive_name}.sha256"
    fields = checksum.read_text(encoding="utf-8").split()
    if len(fields) != 2 or fields[1] != archive_name:
        raise coverage.CoverageError("PostGIS archive checksum file is malformed")
    digest = sha256_file(archive)
    if digest.lower() != fields[0].lower():
        raise coverage.CoverageError("PostGIS archive checksum mismatch")
    core_name = f"postgresql-18.6-{platform_id}.tar.gz"
    core_fields = (core_archives / f"{core_name}.sha256").read_text(encoding="utf-8").split()
    if len(core_fields) != 2 or core_fields[1] != core_name:
        raise coverage.CoverageError("PostgreSQL core checksum file is malformed")
    core_digest = sha256_file(core_archives / core_name)
    if core_digest.lower() != core_fields[0].lower():
        raise coverage.CoverageError("PostgreSQL core archive checksum mismatch")
    if evidence is not None:
        checksums = parse_archive_checksums(evidence / "archive-checksums.sha256")
        if checksums != {archive_name: digest, core_name: core_digest}:
            raise coverage.CoverageError("minimum-kernel evidence archive checksum mismatch")
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
        "outcome": outcome,
        "sha256": digest,
        "assembled_core": {"archive": core_name, "sha256": core_digest, "version": "18.6"},
        "version": "3.6.4",
        "platform": platform_id,
        "postgresql_version": "18.6",
        "environment": {
            "os": "linux",
            "os_version": kernel_match.group(1),
            **({"kernel_release": kernel} if endpoint == "current" or outcome == "passed" else {}),
            **({"distribution": release["PRETTY_NAME"],
                "distribution_version": release["VERSION_ID"]} if release else {}),
            "architecture": architecture,
            "clean_system": outcome == "passed",
            "endpoint": endpoint,
            "image_id": image_id,
            "dependency_check_profile": "postgis-runtime-v1",
            "dependency_checks_passed": outcome == "passed",
        },
    }
    support = coverage.load_json(root / "support.json")
    names = support["extensions"]["PostGIS"]["sql_names"]
    if sorted(names) != ["postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology"]:
        raise coverage.CoverageError("PostGIS SQL names differ from the tested pilot set")
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in names:
        extension_record = {**record, "component": name, "project": "PostGIS"}
        coverage.validate_verification_record(extension_record, support, root)
        suffix = "-minimum" if evidence is not None else ""
        path = output / f"{name}-3.6.4-postgresql-18.6-{platform_id}{suffix}-{run_id}.json"
        path.write_text(json.dumps(extension_record, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", choices=["x86_64", "arm64"], default="x86_64")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--kernel", required=True)
    parser.add_argument("--outcome", choices=("passed", "failed", "skipped"), default="passed")
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.archives, args.core_archives, args.output,
                         args.image_id, args.kernel, args.architecture, args.evidence,
                         args.outcome):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError) as exc:
        print(f"PostGIS pilot record: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
