#!/usr/bin/env python3
"""Emit checksum-bound publication records for pg_jsonschema on Windows x86-64."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile

import coverage
from license_pointer import LicensePointerError, verify_archive as verify_license_pointer
from windows_core_pin import load_identity, PG_VERSIONS
import windows_core_target

PROFILE_ID = "pg-jsonschema-publication-windows-x86_64-18.6"
PG_VERSION = "18.6"
PG_JSONSCHEMA_VERSION = "0.3.4"
ARCHITECTURE = "x86_64"
PLATFORM = "windows-x86_64"
_CORE = load_identity()
CORE_SHA256 = _CORE["sha256"]
CORE_BUILD_ID = _CORE["build_id"]
CORE_SOURCE_REVISION = _CORE["source_revision"]
CORE_STATUS = _CORE["status"]
SOURCE_URL = "https://github.com/supabase/pg_jsonschema.git"
SOURCE_COMMIT = "cbe74b570d38aa0c4d42914e7a118bcb3adaee7a"
CARGO_LOCK_SHA256 = "ab865dc25d9eea4bf7dbfaf8fae13283e5c0bce4bca460fe10464c6716e67028"
CASES = {"archive-suite", "static-analysis"}


def _fail(message):
    raise coverage.CoverageError(message)


def load_core_identity(pg_version, path=None):
    identity = load_identity(path, pg_version)
    if path is None and pg_version == PG_VERSION:
        identity["sha256"] = CORE_SHA256
    return identity


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sidecar(path, digest):
    try:
        lines = Path(str(path) + ".sha256").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fail(f"missing checksum sidecar for {Path(path).name}")
    name = Path(path).name
    if (len(lines) != 1 or not re.fullmatch(rf"[0-9a-fA-F]{{64}}\s+\*?{re.escape(name)}", lines[0])
            or lines[0].split()[0].lower() != digest):
        _fail(f"checksum sidecar does not match {name}")


def _verify_license_pointers(core_archive, extension_archive):
    for archive, component in ((core_archive, "postgresql"), (extension_archive, "pg_jsonschema")):
        try:
            verify_license_pointer(archive, component)
        except LicensePointerError as exc:
            _fail(f"{component} archive licence pointer is invalid: {exc}")


def _json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _fail(f"{label} report is missing or invalid")
    if not isinstance(value, dict):
        _fail(f"{label} report must be a JSON object")
    return value


def _metadata(path, pg_version=PG_VERSION, core_identity=None):
    core_identity = core_identity or load_core_identity(pg_version)
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            item = next((m for m in members if m.name == "metadata.json" and m.isfile()
                         and m.size <= 1024 * 1024), None)
            if item is None:
                _fail("pg_jsonschema archive requires bounded metadata.json")
            value = json.loads(archive.extractfile(item).read().decode("utf-8"))
            names = {m.name for m in members}
            if len(names) != len(members):
                _fail("pg_jsonschema archive contains duplicate paths")
            for member in members:
                path_name = Path(member.name)
                if path_name.is_absolute() or ".." in path_name.parts or member.issym() or member.islnk():
                    _fail("pg_jsonschema archive contains an unsafe path or link")
                if member.isfile() and Path(member.name).suffix.lower() in {".exe", ".so", ".dylib"}:
                    _fail("Windows pg_jsonschema archive contains unexpected native code")
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot inspect pg_jsonschema archive: {exc}")
    expected = {
        "project": "pg_jsonschema", "version": PG_JSONSCHEMA_VERSION, "sql_names": ["pg_jsonschema"],
        "postgresql_version": pg_version, "platform": "windows", "architecture": ARCHITECTURE,
        "source": {"url": SOURCE_URL, "commit": SOURCE_COMMIT,
                   "cargo_lock_sha256": CARGO_LOCK_SHA256},
        "core_archive": {"basename": f"postgresql-{pg_version}-{PLATFORM}.tar.gz",
                         "sha256": core_identity["sha256"]},
        "release_eligible": False, "core_status": core_identity["status"],
    }
    if not isinstance(value, dict) or any(value.get(k) != v for k, v in expected.items()):
        _fail("pg_jsonschema metadata does not match the pinned publication target")


def _step(value, name):
    mapping = {"success": "passed", "failure": "failed", "skipped": "skipped",
               "cancelled": "skipped", "timed_out": "failed"}
    if value not in mapping:
        _fail(f"{name} result must be a GitHub Actions step outcome")
    return mapping[value]


def emit(root, core_dir, archives, output, step_results, os_version, image_id, environ=None,
         postgresql_version=PG_VERSION, core_identity_path=None):
    root, core_dir, archives, output = map(Path, (root, core_dir, archives, output))
    environ = os.environ if environ is None else environ
    if not isinstance(step_results, dict) or set(step_results) != CASES:
        _fail("step_results must identify archive-suite and static-analysis")
    results = {case: _step(step_results[case], case) for case in sorted(CASES)}
    revision, run_id = environ.get("GITHUB_SHA", ""), environ.get("GITHUB_RUN_ID", "")
    repository, server_url = environ.get("GITHUB_REPOSITORY", ""), environ.get("GITHUB_SERVER_URL", "")
    if not coverage.REVISION.fullmatch(revision) or not run_id.isdigit() or not repository or not server_url:
        _fail("GitHub Actions revision and run provenance are required")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version or "") or not image_id:
        _fail("Windows runner version and image identifier are required")
    if postgresql_version not in PG_VERSIONS:
        _fail("unsupported Windows PostgreSQL target")
    profile_id = f"pg-jsonschema-publication-windows-x86_64-{postgresql_version}"
    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or profile["platforms"] != [PLATFORM]
            or profile["case_ids"] != sorted(CASES) or not profile["sources_available"]):
        _fail("registered profile does not match this pg_jsonschema publication suite")
    core_name = f"postgresql-{postgresql_version}-{PLATFORM}.tar.gz"
    extension_name = f"pg_jsonschema-{PG_JSONSCHEMA_VERSION}-postgresql-{postgresql_version}-{PLATFORM}.tar.gz"
    core_archive, extension_archive = core_dir / core_name, archives / extension_name
    archives_present = {core_name: core_archive.is_file(), extension_name: extension_archive.is_file()}
    if all(archives_present.values()):
        core_identity = load_core_identity(postgresql_version, core_identity_path)
        core_identity_known = True
    else:
        try:
            core_identity = load_core_identity(postgresql_version, core_identity_path)
            core_identity_known = True
        except ValueError:
            if core_identity_path is None:
                raise
            target = windows_core_target.load_target(
                core_identity_path, postgresql_version=postgresql_version, root=root)
            core_identity = {"status": target["status"]}
            core_identity_known = False
    publication = output / "publication"
    publication.mkdir(parents=True, exist_ok=True)
    attempt_path = publication / "attempt.json"
    attempt = {
        "schema_version": 1, "run_id": run_id, "source_revision": revision,
        "profile_id": profile_id, "postgresql_version": postgresql_version, "pg_jsonschema_version": PG_JSONSCHEMA_VERSION,
        "architecture": ARCHITECTURE, "steps": {c: step_results[c] for c in sorted(CASES)},
        "release_eligible": False, "core_status": core_identity["status"],
        "core_identity_known": core_identity_known,
        "archives_present": archives_present,
    }
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not core_archive.is_file() or not extension_archive.is_file():
        return [attempt_path]
    digests = {core_name: sha256_file(core_archive), extension_name: sha256_file(extension_archive)}
    attempt["archives"] = digests
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for archive in (core_archive, extension_archive):
        _sidecar(archive, digests[archive.name])
    if digests[core_name] != core_identity["sha256"]:
        _fail("PostgreSQL core archive does not match the selected successful Windows build")
    _verify_license_pointers(core_archive, extension_archive)
    _metadata(extension_archive, postgresql_version, core_identity)
    static_path, probe_path = output / "static-analysis.json", output / "probe-output.txt"
    reports = {name: sha256_file(path) for name, path in
               (("static_analysis", static_path), ("probe_output", probe_path),
                ("first_run_probe_output", output / "first-run-probe-output.txt"),
                ("pe_dependency_analysis", output / "pe-dependency-analysis.json")) if path.is_file()}
    if results["archive-suite"] == "passed":
        if not probe_path.is_file():
            _fail("archive suite did not retain its pg_jsonschema output")
        if "pg_jsonschema" not in probe_path.read_text(encoding="utf-8"):
            _fail("archive suite output does not identify the installed extension")
        first_probe = output / "first-run-probe-output.txt"
        if (not first_probe.is_file()
                or "pg_jsonschema" not in first_probe.read_text(encoding="utf-8")):
            _fail("first archive-suite output does not identify the installed extension")
    if results["static-analysis"] == "passed":
        static = _json(static_path, "static analysis")
        if (static.get("passed") is not True or static.get("architecture") != ARCHITECTURE
                or static.get("archives") != digests or not static.get("inspected_files")
                or static.get("native_extension_files") != ["pg_jsonschema/lib/pg_jsonschema.dll"]
                or not re.fullmatch(r"[0-9a-f]{64}", str(static.get("pe_dependency_analysis_sha256", "")))):
            _fail("static analysis did not pass over the exact final archives")
    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    receipt = {
        "schema_version": 1, "profile_id": profile_id, "profile_revision": profile["profile_revision"],
        "test_revision": revision, "project": "pg_jsonschema", "version": PG_JSONSCHEMA_VERSION,
        "postgresql_version": postgresql_version, "architecture": ARCHITECTURE, "platform": PLATFORM,
        "endpoint": "current", "case_results": results, "archives": digests,
        "extension_archive": extension_name, "reports": reports, "clean_system": True,
        "dependency_check_profile": "windows-sql-archive-relocation-v1",
        "dependency_checks_passed": results["static-analysis"] == "passed",
        "release_eligible": False, "core_status": core_identity["status"],
        "environment": {"os": "windows", "os_version": os_version, "architecture": ARCHITECTURE,
                        "image_id": image_id},
        "ci": ci,
    }
    receipt_path = publication / "current-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = {
        "schema_version": 2, "scope": "publication", "profile_id": profile_id,
        "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
        "case_results": results, "test_revision": revision, "ci": ci, "outcome": outcome,
        "sha256": digests[extension_name], "component": "pg_jsonschema", "project": "pg_jsonschema",
        "version": PG_JSONSCHEMA_VERSION, "platform": PLATFORM, "postgresql_version": postgresql_version,
        "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": postgresql_version},
        "prerequisite_archives": [],
        "release_eligible": False, "core_status": core_identity["status"],
        "environment": {"os": "windows", "os_version": os_version, "architecture": ARCHITECTURE,
                        "clean_system": True, "endpoint": "current", "image_id": image_id,
                        "dependency_check_profile": receipt["dependency_check_profile"],
                        "dependency_checks_passed": receipt["dependency_checks_passed"]},
    }
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    records = publication / "records"
    records.mkdir(parents=True, exist_ok=True)
    path = records / f"pg_jsonschema-{PG_JSONSCHEMA_VERSION}-postgresql-{postgresql_version}-{PLATFORM}-current-{run_id}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [attempt_path, receipt_path, path]


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
    parser.add_argument("--postgresql-version", choices=PG_VERSIONS, default=PG_VERSION)
    parser.add_argument("--core-identity", type=Path)
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.core_archives, args.archives, args.output,
                         {"archive-suite": args.archive_suite_result,
                          "static-analysis": args.static_analysis_result},
                         args.os_version, args.image_id, postgresql_version=args.postgresql_version,
                         core_identity_path=args.core_identity):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_jsonschema Windows publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
