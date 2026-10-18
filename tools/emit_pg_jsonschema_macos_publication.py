#!/usr/bin/env python3
"""Emit archive-bound candidate evidence for macOS pg_jsonschema."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile

import coverage

from pg_jsonschema_macos_target import load_target

CORE_STATUS = "current-profile-core-redistribution-pending"
RELEASE_BLOCKERS = ["seahash-4.1.0-notice-unresolved",
                    "postgresql-core-redistribution-review-pending"]
CASES = {"archive-suite", "static-analysis"}
ALLOWED_STEPS = {"success", "failure", "skipped", "cancelled", "timed_out"}
TARGET = None


def configure_target(path):
    global TARGET, PROFILE_ID, PG_VERSION, EXTENSION_VERSION, ARCHITECTURE, PLATFORM
    global SOURCE_URL, SOURCE_COMMIT, CARGO_LOCK_SHA256
    global CORE_RUN_ID, CORE_SHA256, CORE_BUILD_ID, CORE_SOURCE_REVISION
    global MODULE_FILENAME, MODULE_PATH
    TARGET = load_target(path)
    PROFILE_ID, PG_VERSION, EXTENSION_VERSION = (TARGET.profile_id, TARGET.postgresql_version,
                                                  TARGET.extension_version)
    ARCHITECTURE, PLATFORM = TARGET.architecture, TARGET.platform
    SOURCE_URL, SOURCE_COMMIT = TARGET.source_url, TARGET.source_commit
    CARGO_LOCK_SHA256 = TARGET.cargo_lock_sha256
    CORE_RUN_ID, CORE_SHA256 = TARGET.core_run_id, TARGET.core_sha256
    CORE_BUILD_ID, CORE_SOURCE_REVISION = TARGET.core_build_id, TARGET.core_source_revision
    MODULE_FILENAME = TARGET.module_filename
    MODULE_PATH = f"lib/{MODULE_FILENAME}"
    return TARGET


DEFAULT_TARGET = Path(__file__).resolve().parent / "pg_jsonschema_macos_targets/18.6-x86_64.json"
configure_target(DEFAULT_TARGET)


def _fail(message):
    raise coverage.CoverageError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"{label} is missing or invalid: {exc}")
    if not isinstance(value, dict):
        _fail(f"{label} must be a JSON object")
    return value


def _sidecar(path, digest):
    path = Path(path)
    try:
        lines = Path(str(path) + ".sha256").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fail(f"missing checksum sidecar for {path.name}")
    if (len(lines) != 1
            or not re.fullmatch(rf"[0-9a-f]{{64}}  {re.escape(path.name)}", lines[0])
            or lines[0].split()[0] != digest):
        _fail(f"checksum sidecar does not match {path.name}")


def _metadata(path):
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                _fail("pg_jsonschema archive contains duplicate paths")
            for member in members:
                name = Path(member.name)
                if name.is_absolute() or ".." in name.parts or member.issym() or member.islnk():
                    _fail("pg_jsonschema archive contains an unsafe path or link")
            metadata = next((member for member in members if member.name == "metadata.json"
                             and member.isfile() and member.size <= 1024 * 1024), None)
            if metadata is None:
                _fail("pg_jsonschema archive requires bounded metadata.json")
            value = json.loads(archive.extractfile(metadata).read().decode("utf-8"))
            native = sorted(member.name for member in members if member.isfile()
                            and member.name.startswith("pg_jsonschema/lib/"))
            required = {f"pg_jsonschema/{MODULE_PATH}",
                        "pg_jsonschema/share/extension/pg_jsonschema.control",
                        "pg_jsonschema/LICENSES/pg_jsonschema.txt",
                        "pg_jsonschema/LICENSES/pg_jsonschema-cargo-license-inventory.json"}
            if not required <= set(names) or native != [f"pg_jsonschema/{MODULE_PATH}"]:
                _fail("pg_jsonschema archive payload is incomplete or contains extra native code")
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot inspect final pg_jsonschema archive: {exc}")
    expected = {
        "project": "pg_jsonschema", "version": EXTENSION_VERSION, "sql_names": ["pg_jsonschema"],
        "requires": [], "postgresql_version": PG_VERSION, "platform": "macos",
        "architecture": ARCHITECTURE,
        "source": {"url": SOURCE_URL, "commit": SOURCE_COMMIT,
                   "cargo_lock_sha256": CARGO_LOCK_SHA256},
        "core_archive": {"basename": f"postgresql-{PG_VERSION}-{PLATFORM}.tar.gz",
                         "sha256": CORE_SHA256},
        "release_eligible": False, "release_blockers": RELEASE_BLOCKERS,
    }
    if value != expected:
        _fail("pg_jsonschema metadata differs from the pinned candidate identity")


def _step(value, name):
    mapping = {"success": "passed", "failure": "failed", "timed_out": "failed",
               "skipped": "skipped", "cancelled": "skipped"}
    if value not in mapping:
        _fail(f"{name} must be a GitHub Actions step outcome")
    return mapping[value]


def _static_report(path, digests):
    report = _json(path, "Mach-O static analysis report")
    actual = report.get("archives")
    if isinstance(actual, list):
        try:
            actual = {item["basename"]: item["sha256"] for item in actual}
        except (KeyError, TypeError):
            actual = None
    files = report.get("inspected_files", [])
    if (report.get("passed") is not True or report.get("architecture") != ARCHITECTURE
            or actual != digests
            or not any(item.get("file") == MODULE_PATH
                       for item in files if isinstance(item, dict))):
        _fail("Mach-O static report does not pass for the exact core and extension archives")
    return report


def emit(root, core_dir, archives, output, step_results, os_version, image_id, environ=None, target_config=None):
    if target_config is not None:
        configure_target(target_config)
    root, core_dir, archives, output = map(Path, (root, core_dir, archives, output))
    environ = os.environ if environ is None else environ
    if not isinstance(step_results, dict) or set(step_results) != CASES or any(
            value not in ALLOWED_STEPS for value in step_results.values()):
        _fail("step_results must identify archive-suite and static-analysis outcomes")
    results = {case: _step(step_results[case], case) for case in sorted(CASES)}
    revision, run_id = environ.get("GITHUB_SHA", ""), environ.get("GITHUB_RUN_ID", "")
    repository, server_url = environ.get("GITHUB_REPOSITORY", ""), environ.get("GITHUB_SERVER_URL", "")
    if not coverage.REVISION.fullmatch(revision) or not run_id.isdigit() or not repository or not server_url:
        _fail("GitHub Actions revision and run provenance are required")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version or "") or not image_id:
        _fail("macOS runner version and image identity are required")
    profile = coverage.verification_profile(root, PROFILE_ID)
    if (profile["scope"] != "publication" or profile["platforms"] != [PLATFORM]
            or profile["case_ids"] != sorted(CASES) or not profile["sources_available"]):
        _fail("registered profile does not match this pg_jsonschema publication suite")
    core_name = f"postgresql-{PG_VERSION}-{PLATFORM}.tar.gz"
    extension_name = f"pg_jsonschema-{EXTENSION_VERSION}-postgresql-{PG_VERSION}-{PLATFORM}.tar.gz"
    core, extension = core_dir / core_name, archives / extension_name
    publication_dir = output / "publication"
    publication_dir.mkdir(parents=True, exist_ok=True)
    attempt_path = publication_dir / "attempt.json"
    attempt = {
        "schema_version": 1, "run_id": run_id, "source_revision": revision,
        "profile_id": PROFILE_ID, "postgresql_version": PG_VERSION,
        "pg_jsonschema_version": EXTENSION_VERSION, "architecture": ARCHITECTURE,
        "core_run_id": CORE_RUN_ID, "steps": {case: step_results[case] for case in sorted(CASES)},
        "archives_present": {core_name: core.is_file(), extension_name: extension.is_file()},
        "release_eligible": False, "core_status": CORE_STATUS,
        "release_blockers": RELEASE_BLOCKERS,
    }
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not core.is_file() or not extension.is_file():
        return [attempt_path]
    digests = {core_name: sha256(core), extension_name: sha256(extension)}
    for archive in (core, extension):
        _sidecar(archive, digests[archive.name])
    if (not all((CORE_SHA256, CORE_BUILD_ID, CORE_SOURCE_REVISION))
            or digests[core_name] != CORE_SHA256):
        _fail("PostgreSQL core archive differs from the selected passed build")
    _metadata(extension)
    attempt["archives"] = digests
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    static_path, probe_path = output / "static-analysis.json", output / "probe-output.txt"
    build_path, license_path = output / "build-evidence.txt", output / "cargo-license-inventory.json"
    reports = {name: sha256(path) for name, path in {
        "static_analysis": static_path, "probe_output": probe_path,
        "build_evidence": build_path, "cargo_license_inventory": license_path,
    }.items() if path.is_file()}
    if results["archive-suite"] == "passed":
        if not probe_path.is_file() or "pg_jsonschema|0.3.4" not in probe_path.read_text(encoding="utf-8"):
            _fail("passing archive suite lacks its pg_jsonschema 0.3.4 SQL output")
    if results["static-analysis"] == "passed":
        _static_report(static_path, digests)
    attempt["reports"] = reports
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if any(result != "passed" for result in results.values()):
        return [attempt_path]
    build_text = build_path.read_text(encoding="utf-8") if build_path.is_file() else ""
    if (f"pg_jsonschema_source_commit={SOURCE_COMMIT}" not in build_text
            or f"cargo_lock_sha256={CARGO_LOCK_SHA256}" not in build_text
            or f"core_run_id={CORE_RUN_ID}" not in build_text
            or f"core_build_id={CORE_BUILD_ID}" not in build_text
            or f"core_source_revision={CORE_SOURCE_REVISION}" not in build_text
            or f"core_sha256={CORE_SHA256}" not in build_text):
        _fail("build evidence does not identify the exact source, Cargo.lock and core archive")
    if "static_analysis" not in reports or "cargo_license_inventory" not in reports:
        _fail("candidate is missing static analysis or Cargo license inventory evidence")

    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    environment = {"os": "macos", "os_version": os_version, "architecture": ARCHITECTURE,
                   "clean_system": True, "endpoint": "current", "image_id": image_id,
                   "dependency_check_profile": "macho-system-dependencies-v1",
                   "dependency_checks_passed": results["static-analysis"] == "passed"}
    receipt = {
        "schema_version": 1, "profile_id": PROFILE_ID,
        "profile_revision": profile["profile_revision"], "test_revision": revision,
        "project": "pg_jsonschema", "version": EXTENSION_VERSION,
        "postgresql_version": PG_VERSION, "architecture": ARCHITECTURE,
        "platform": PLATFORM, "endpoint": "current", "case_results": results,
        "archives": digests, "extension_archive": extension_name, "reports": reports,
        "clean_system": True, "dependency_check_profile": "macho-system-dependencies-v1",
        "dependency_checks_passed": results["static-analysis"] == "passed",
        "release_eligible": False, "core_status": CORE_STATUS,
        "release_blockers": RELEASE_BLOCKERS, "environment": environment, "ci": ci,
    }
    receipt_path = publication_dir / "current-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = {
        "schema_version": 2, "scope": "publication", "profile_id": PROFILE_ID,
        "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
        "case_results": results, "test_revision": revision, "ci": ci, "outcome": outcome,
        "sha256": digests[extension_name], "component": "pg_jsonschema", "project": "pg_jsonschema",
        "version": EXTENSION_VERSION, "platform": PLATFORM, "postgresql_version": PG_VERSION,
        "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": PG_VERSION},
        "prerequisite_archives": [], "release_eligible": False, "core_status": CORE_STATUS,
        "release_blockers": RELEASE_BLOCKERS, "environment": environment,
    }
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    records = publication_dir / "records"
    records.mkdir(parents=True, exist_ok=True)
    record_path = records / f"pg_jsonschema-{EXTENSION_VERSION}-postgresql-{PG_VERSION}-{PLATFORM}-current-{run_id}.json"
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
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--archive-suite-result", required=True)
    parser.add_argument("--static-analysis-result", required=True)
    args = parser.parse_args()
    try:
        configure_target(args.target)
        for path in emit(args.root, args.core_archives, args.archives, args.output,
                         {"archive-suite": args.archive_suite_result,
                          "static-analysis": args.static_analysis_result},
                         args.os_version, args.image_id):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_jsonschema macOS publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
