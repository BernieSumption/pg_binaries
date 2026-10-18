#!/usr/bin/env python3
"""Emit archive-bound candidate evidence for Linux pg_jsonschema."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import coverage

PG_VERSION = "18.6"
EXTENSION_VERSION = "0.3.4"
SOURCE_COMMIT = "cbe74b570d38aa0c4d42914e7a118bcb3adaee7a"
CARGO_LOCK_SHA256 = "ab865dc25d9eea4bf7dbfaf8fae13283e5c0bce4bca460fe10464c6716e67028"
PROFILE_IDS = {
    "x86_64": "pg-jsonschema-publication-linux-x86_64-18.6",
    "arm64": "pg-jsonschema-publication-linux-arm64-18.6",
}
CORE_RUN_ID = "39081368117"
CORE_SHA256 = {
    "x86_64": "f89a7047812324b85c3b0bb29a3118fc55a492b17956f1fe0d74d1788d33d680",
    "arm64": "0eb9c0144fd0b1669c594ce1ebcf7abdf4e1ae3f8e29e59a92833e476001e42b",
}
CASES = ("archive-suite", "elf-closure")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"invalid or missing JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"JSON evidence must be an object: {path}")
    return value


def emit(root, archives, core_archives, output, architecture, build_result,
         verify_result, source_revision, run_id, repository, server_url, image_id):
    root, archives, core_archives, output = map(Path, (root, archives, core_archives, output))
    if architecture not in PROFILE_IDS:
        raise coverage.CoverageError("architecture must be x86_64 or arm64")
    if not coverage.REVISION.fullmatch(source_revision or "") or not str(run_id).isdigit():
        raise coverage.CoverageError("full source revision and numeric workflow run ID are required")
    if not repository or not server_url or not image_id:
        raise coverage.CoverageError("GitHub and runner image provenance are required")
    static_path = archives / "static-analysis" / "pg_jsonschema.json"
    _step(build_result)
    static_outcome = read_json(static_path).get("outcome") if static_path.is_file() else None
    raw_archive_result, raw_elf_result = _case_results(verify_result, static_outcome)
    results = {"archive-suite": _step(raw_archive_result), "elf-closure": _step(raw_elf_result)}
    profile = coverage.verification_profile(root, PROFILE_IDS[architecture])
    platform = f"linux-{architecture}"
    archive_name = f"pg_jsonschema-{EXTENSION_VERSION}-postgresql-{PG_VERSION}-{platform}.tar.gz"
    core_name = f"postgresql-{PG_VERSION}-{platform}.tar.gz"
    archive, core = archives / archive_name, core_archives / core_name
    output.mkdir(parents=True, exist_ok=True)
    attempt_path = output / "attempt.json"
    attempt = {
        "schema_version": 1, "run_id": str(run_id), "source_revision": source_revision,
        "profile_id": PROFILE_IDS[architecture], "postgresql_version": PG_VERSION,
        "pg_jsonschema_version": EXTENSION_VERSION, "architecture": architecture,
        "core_run_id": CORE_RUN_ID,
        "steps": {"archive-suite": raw_archive_result, "elf-closure": raw_elf_result},
        "workflow_steps": {"build": build_result, "verify": verify_result},
        "release_eligible": False, "redistribution_status": "seahash-4.1.0-notice-unresolved",
        "archives_present": {core_name: core.is_file(), archive_name: archive.is_file()},
        "reports": {"elf_closure": digest(static_path)} if static_path.is_file() else {},
    }
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not archive.is_file() or not core.is_file():
        return (attempt_path,)
    checksums = {archive_name: digest(archive), core_name: digest(core)}
    _sidecar(archive, checksums[archive_name])
    _sidecar(core, checksums[core_name])
    attempt["archives"] = checksums
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if checksums[core_name] != CORE_SHA256[architecture]:
        raise coverage.CoverageError("core archive differs from the pinned current PostgreSQL 18.6 archive")
    static = read_json(static_path)
    static_archives = static.get("archives", [])
    if (static.get("outcome") != "passed" or static.get("architecture") != architecture
            or {item.get("basename"): item.get("sha256") for item in static_archives} != {archive_name: checksums[archive_name]}):
        raise coverage.CoverageError("ELF closure report does not pass for the exact final archive")
    build_text = (archives / "build-evidence.txt").read_text(encoding="utf-8")
    if (f"pg_jsonschema_source_commit={SOURCE_COMMIT}" not in build_text
            or f"cargo_lock_sha256={CARGO_LOCK_SHA256}" not in build_text):
        raise coverage.CoverageError("build evidence does not identify the pinned source and Cargo.lock")
    attempt["reports"].update({"build_evidence": digest(archives / "build-evidence.txt"),
                               "cargo_license_inventory": digest(archives / "cargo-license-inventory.json")})
    probe_output = archives / "probe-output.txt"
    if probe_output.is_file():
        attempt["reports"]["probe_output"] = digest(probe_output)
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ci = {"provider": "github-actions", "run_id": str(run_id),
          "run_url": f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}",
          "source_revision": source_revision, "build_revision": source_revision,
          "test_revision": source_revision}
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    reports = {"elf_closure": digest(static_path),
               "build_evidence": digest(archives / "build-evidence.txt"),
               "cargo_license_inventory": digest(archives / "cargo-license-inventory.json")}
    if probe_output.is_file():
        reports["probe_output"] = digest(probe_output)
    environment = {"os": "linux", "os_version": "3.22", "distribution": "Alpine Linux",
                   "architecture": architecture, "clean_system": True, "endpoint": "current",
                   "image_id": image_id, "dependency_check_profile": "linux-elf-alpine-relocation-v1",
                   "dependency_checks_passed": results["elf-closure"] == "passed"}
    receipt = {
        "schema_version": 1, "profile_id": PROFILE_IDS[architecture],
        "profile_revision": profile["profile_revision"], "test_revision": source_revision,
        "project": "pg_jsonschema", "version": EXTENSION_VERSION, "postgresql_version": PG_VERSION,
        "architecture": architecture, "platform": platform, "endpoint": "current",
        "case_results": results, "archives": checksums, "extension_archive": archive_name,
        "reports": reports, "clean_system": True,
        "dependency_check_profile": "linux-elf-alpine-relocation-v1",
        "dependency_checks_passed": results["elf-closure"] == "passed",
        "release_eligible": False, "redistribution_status": "seahash-4.1.0-notice-unresolved",
        "environment": environment, "ci": ci,
    }
    receipt_path = output / "current-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = {
        "schema_version": 2, "scope": "publication", "profile_id": PROFILE_IDS[architecture],
        "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
        "case_results": results, "test_revision": source_revision, "ci": ci, "outcome": outcome,
        "sha256": checksums[archive_name], "component": "pg_jsonschema", "project": "pg_jsonschema",
        "version": EXTENSION_VERSION, "platform": platform, "postgresql_version": PG_VERSION,
        "assembled_core": {"archive": core_name, "sha256": checksums[core_name], "version": PG_VERSION},
        "prerequisite_archives": [], "release_eligible": False,
        "redistribution_status": "seahash-4.1.0-notice-unresolved",
        "environment": environment,
    }
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    record_path = output / "verification-record.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return attempt_path, receipt_path, record_path


def _step(value):
    mapping = {"success": "passed", "failure": "failed", "skipped": "skipped",
               "cancelled": "skipped", "timed_out": "failed"}
    if value not in mapping:
        raise coverage.CoverageError("step result must be a GitHub Actions outcome")
    return mapping[value]


def _case_results(verify_result, elf_outcome):
    if verify_result not in {"success", "failure", "skipped", "cancelled", "timed_out"}:
        raise coverage.CoverageError("verify result must be a GitHub Actions outcome")
    elf_result = ("success" if elf_outcome == "passed" else "failure") if elf_outcome is not None else "skipped"
    archive_result = ("success" if verify_result == "success" else
                      "failure" if verify_result in {"failure", "timed_out"} and elf_result == "success" else "skipped")
    return archive_result, elf_result


def _sidecar(path, expected):
    sidecar = Path(str(path) + ".sha256")
    try:
        lines = sidecar.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise coverage.CoverageError(f"missing checksum sidecar for {path.name}") from exc
    if len(lines) != 1 or not re.fullmatch(rf"{expected}\s+\*?{re.escape(path.name)}", lines[0]):
        raise coverage.CoverageError(f"checksum sidecar does not match {path.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--architecture", choices=tuple(PROFILE_IDS), required=True)
    parser.add_argument("--build-result", required=True)
    parser.add_argument("--verify-result", required=True)
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args()
    try:
        env = os.environ
        for path in emit(args.root, args.archives, args.core_archives, args.output, args.architecture,
                         args.build_result, args.verify_result, env.get("GITHUB_SHA", ""),
                         env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_REPOSITORY", ""),
                         env.get("GITHUB_SERVER_URL", ""), args.image_id):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_jsonschema Linux publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
