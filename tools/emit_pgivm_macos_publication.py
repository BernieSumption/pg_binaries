#!/usr/bin/env python3
"""Bind the pg_ivm macOS arm64 archive and feasibility checks into records."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tarfile

import coverage
import macos_publication_evidence as evidence
from check_macos_extension_license_inventory import check_archive


PROFILE_ID = "pgivm-publication-macos-arm64-18.6"
PG_VERSION = "18.6"
PGIVM_VERSION = "1.16"
ARCHITECTURE = "arm64"
PLATFORM = "macos-arm64"
CORE_SHA256 = "ec3f624ecfbea6dad20672106ec11bfafadde42e0454bc90bef992caa4be0033"
SOURCE_URL = "https://github.com/sraoss/pg_ivm/archive/refs/tags/v1.16.tar.gz"
SOURCE_SHA256 = "87807d6af1974fce591715d55f75d939dffea33ea6908b413e62d3dd79b9c583"
CASES = {"archive-suite", "static-analysis"}


def _fail(message):
    raise coverage.CoverageError(message)


def sha256_file(path):
    return evidence.sha256_file(path)


def _sidecar(path, digest):
    evidence.check_sidecar(path, digest, "missing checksum sidecar for {name}")


def _metadata(path):
    try:
        with tarfile.open(path, "r:gz") as archive:
            member = next((item for item in archive.getmembers()
                           if item.name == "metadata.json" and item.isfile()
                           and item.size <= 1024 * 1024), None)
            if member is None:
                _fail("pg_ivm archive requires bounded metadata.json")
            value = json.loads(archive.extractfile(member).read().decode("utf-8"))
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read pg_ivm archive metadata: {exc}")
    expected = {
        "project": "pg_ivm", "version": PGIVM_VERSION, "sql_names": ["pg_ivm"],
        "postgresql_version": PG_VERSION, "platform": "macos", "architecture": ARCHITECTURE,
        "source": {"url": SOURCE_URL, "sha256": SOURCE_SHA256},
        "core_archive": {"basename": f"postgresql-{PG_VERSION}-{PLATFORM}.tar.gz",
                         "sha256": CORE_SHA256},
    }
    if not isinstance(value, dict) or any(value.get(key) != item for key, item in expected.items()):
        _fail("pg_ivm metadata does not match the pinned publication target")


def _json(path, label):
    try:
        return evidence.read_json_object(path)
    except coverage.CoverageError as exc:
        _fail(f"{label} report is missing or invalid: {exc}")


def _step_result(value, name):
    mapping = {"success": "passed", "failure": "failed", "skipped": "skipped",
               "cancelled": "skipped", "timed_out": "failed"}
    if value not in mapping:
        _fail(f"{name} result must be a GitHub Actions step outcome")
    return mapping[value]


def emit(root, core_dir, archives, output, step_results, os_version, image_id, environ=None):
    root, core_dir, archives, output = map(Path, (root, core_dir, archives, output))
    environ = os.environ if environ is None else environ
    if not isinstance(step_results, dict) or set(step_results) != CASES:
        _fail("step_results must identify archive-suite and static-analysis")
    results = {case: _step_result(step_results[case], case) for case in sorted(CASES)}
    outcome = ("failed" if "failed" in results.values()
               else "skipped" if "skipped" in results.values() else "passed")
    revision = environ.get("GITHUB_SHA", "")
    run_id = environ.get("GITHUB_RUN_ID", "")
    repository = environ.get("GITHUB_REPOSITORY", "")
    server_url = environ.get("GITHUB_SERVER_URL", "")
    if (not coverage.REVISION.fullmatch(revision) or not run_id.isdigit()
            or not repository or not server_url):
        _fail("GitHub Actions revision and run provenance are required")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version or "") or not image_id:
        _fail("macOS runner version and image identifier are required")

    profile = coverage.verification_profile(root, PROFILE_ID)
    if (profile["scope"] != "publication" or profile["platforms"] != [PLATFORM]
            or profile["case_ids"] != sorted(CASES) or not profile["sources_available"]):
        _fail("registered profile does not match this pg_ivm publication suite")
    core_name = f"postgresql-{PG_VERSION}-{PLATFORM}.tar.gz"
    extension_name = f"pg_ivm-{PGIVM_VERSION}-postgresql-{PG_VERSION}-{PLATFORM}.tar.gz"
    core_archive, extension_archive = core_dir / core_name, archives / extension_name
    attempt = {
        "schema_version": 1, "run_id": run_id, "source_revision": revision,
        "profile_id": PROFILE_ID, "postgresql_version": PG_VERSION,
        "pg_ivm_version": PGIVM_VERSION, "architecture": ARCHITECTURE,
        "steps": {case: step_results[case] for case in sorted(CASES)},
        "archives_present": {core_name: core_archive.is_file(), extension_name: extension_archive.is_file()},
    }
    publication = output / "publication"
    publication.mkdir(parents=True, exist_ok=True)
    attempt_path = publication / "attempt.json"
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not core_archive.is_file() or not extension_archive.is_file():
        return [attempt_path]

    digests = {core_name: sha256_file(core_archive), extension_name: sha256_file(extension_archive)}
    _sidecar(core_archive, digests[core_name])
    _sidecar(extension_archive, digests[extension_name])
    if digests[core_name] != CORE_SHA256:
        _fail("PostgreSQL core archive does not match the selected passed build")
    _metadata(extension_archive)
    try:
        components, native_files = check_archive(extension_archive)
    except (OSError, ValueError) as exc:
        _fail(f"final pg_ivm archive licence inventory is invalid: {exc}")
    if components != 1 or native_files < 1:
        _fail("final pg_ivm archive must inventory its native payload and licence")
    attempt["archives"] = digests
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    static_path = output / "static-analysis.json"
    probe_path = output / "probe-output.txt"
    report_paths = {"static_analysis": static_path, "probe_output": probe_path}
    report_digests = {name: sha256_file(path) for name, path in report_paths.items() if path.is_file()}
    if results["archive-suite"] == "passed":
        if not probe_path.is_file():
            _fail("passing archive suite is missing pg_ivm probe output")
        probe = probe_path.read_text(encoding="utf-8")
        if ("CREATE EXTENSION" not in probe or "CREATE TABLE" not in probe
                or "create_immv" not in probe or probe.count("DO") < 3
                or not re.search(r"(?m)^\s*18\.6\s*$", probe)):
            _fail("pg_ivm probe output does not show the expected extension and IMMV checks")
    if results["static-analysis"] == "passed":
        static = _json(static_path, "static analysis")
        actual = static.get("archives")
        if isinstance(actual, list):
            try:
                actual = {item["basename"]: item["sha256"] for item in actual}
            except (KeyError, TypeError):
                actual = None
        if (actual != digests or static.get("passed") is not True
                or static.get("architecture") != ARCHITECTURE
                or not static.get("inspected_files")):
            _fail("static analysis did not pass over the final assembled archives")

    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    receipt = {
        "schema_version": 1, "profile_id": PROFILE_ID,
        "profile_revision": profile["profile_revision"], "test_revision": revision,
        "project": "pg_ivm", "version": PGIVM_VERSION,
        "postgresql_version": PG_VERSION, "architecture": ARCHITECTURE,
        "platform": PLATFORM, "endpoint": "current", "case_results": results,
        "archives": digests, "extension_archive": extension_name, "reports": report_digests,
        "clean_system": True, "dependency_check_profile": "macho-system-dependencies-v1",
        "dependency_checks_passed": (_json(static_path, "static analysis").get("passed") is True
                                      if static_path.is_file() else False),
        "environment": {"os": "macos", "os_version": os_version,
                        "architecture": ARCHITECTURE, "image_id": image_id},
        "ci": ci,
    }
    receipt_path = publication / "current-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = {
        "schema_version": 2, "scope": "publication", "profile_id": PROFILE_ID,
        "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
        "case_results": results, "test_revision": revision, "ci": ci,
        "outcome": outcome, "sha256": digests[extension_name],
        "component": "pg_ivm", "project": "pg_ivm", "version": PGIVM_VERSION,
        "platform": PLATFORM, "postgresql_version": PG_VERSION,
        "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": PG_VERSION},
        "prerequisite_archives": [],
        "environment": {"os": "macos", "os_version": os_version,
                        "architecture": ARCHITECTURE, "clean_system": True,
                        "endpoint": "current", "image_id": image_id,
                        "dependency_check_profile": receipt["dependency_check_profile"],
                        "dependency_checks_passed": receipt["dependency_checks_passed"]},
    }
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    records = publication / "records"
    records.mkdir(parents=True, exist_ok=True)
    record_path = records / f"pg_ivm-{PGIVM_VERSION}-postgresql-{PG_VERSION}-{PLATFORM}-current-{run_id}.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [attempt_path, receipt_path, record_path]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--archive-suite-result", required=True)
    parser.add_argument("--static-analysis-result", required=True)
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.core_archives, args.archives, args.output,
                         {"archive-suite": args.archive_suite_result,
                          "static-analysis": args.static_analysis_result},
                         args.os_version, args.image_id):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_ivm macOS publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
