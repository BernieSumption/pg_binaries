#!/usr/bin/env python3
"""Bind the pgAudit macOS arm64 archive, checks and CI attempt into records."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile

import coverage
from pgaudit_macos_targets import target


ARCHITECTURE = "arm64"
PLATFORM = "macos-arm64"
CASES = {"archive-suite", "symbols", "diagnostics"}


def _fail(message):
    raise coverage.CoverageError(message)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sidecar(path, digest):
    path = Path(path)
    try:
        lines = path.with_name(path.name + ".sha256").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fail(f"missing checksum sidecar for {path.name}")
    if (len(lines) != 1
            or not re.fullmatch(rf"[0-9a-fA-F]{{64}}\s+\*?{re.escape(path.name)}", lines[0])
            or lines[0].split()[0].lower() != digest):
        _fail(f"checksum sidecar does not match {path.name}")


def _json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"{label} report is missing or invalid")
    if not isinstance(value, dict):
        _fail(f"{label} report must be a JSON object")
    return value


def _archive_metadata(path, selected):
    try:
        with tarfile.open(path, "r:gz") as archive:
            member = next((item for item in archive.getmembers()
                           if item.name == "metadata.json" and item.isfile()
                           and item.size <= 1024 * 1024), None)
            if member is None:
                _fail("pgAudit archive requires bounded metadata.json")
            value = json.loads(archive.extractfile(member).read().decode("utf-8"))
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read pgAudit archive metadata: {exc}")
    expected = {
        "project": "pgaudit", "version": selected["pgaudit_version"], "sql_names": ["pgaudit"],
        "postgresql_version": selected["postgresql_version"], "platform": "macos", "architecture": ARCHITECTURE,
        "source": {"url": selected["source_url"], "sha256": selected["source_sha256"]},
        "core_archive": {
            "basename": f"postgresql-{selected['postgresql_version']}-{PLATFORM}.tar.gz",
            "sha256": selected["core_sha256"],
        },
    }
    if not isinstance(value, dict) or any(value.get(key) != item for key, item in expected.items()):
        _fail("pgAudit metadata does not match the pinned publication target")
    return value


def _archive_report(report, digests, label):
    actual = report.get("archives")
    if isinstance(actual, list):
        try:
            actual = {item["basename"]: item["sha256"] for item in actual}
        except (KeyError, TypeError):
            actual = None
    if not isinstance(actual, dict) or actual != digests:
        _fail(f"{label} report archive hashes do not match the final archive bytes")


def _step_result(value, name):
    mapping = {"success": "passed", "failure": "failed", "skipped": "skipped",
               "cancelled": "skipped", "timed_out": "failed"}
    if value not in mapping:
        _fail(f"{name} result must be a GitHub Actions step outcome")
    return mapping[value]


def emit(root, core_dir, archives, output, step_results, os_version, image_id, environ=None, pg_version="18.6"):
    selected = target(pg_version)
    profile_id = selected["profile_id"]
    pgaudit_version = selected["pgaudit_version"]
    root, core_dir, archives, output = map(Path, (root, core_dir, archives, output))
    environ = os.environ if environ is None else environ
    if not isinstance(step_results, dict) or set(step_results) != CASES:
        _fail("step_results must identify archive-suite, symbols, and diagnostics")
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

    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or PLATFORM not in profile["platforms"]
            or profile["case_ids"] != sorted(CASES) or not profile["sources_available"]):
        _fail("registered profile does not match this pgAudit publication suite")
    core_name = f"postgresql-{pg_version}-{PLATFORM}.tar.gz"
    extension_name = f"pgaudit-{pgaudit_version}-postgresql-{pg_version}-{PLATFORM}.tar.gz"
    core_archive, extension_archive = core_dir / core_name, archives / extension_name
    attempt = {
        "schema_version": 1, "run_id": run_id, "source_revision": revision,
        "profile_id": profile_id, "postgresql_version": pg_version,
        "pgaudit_version": pgaudit_version, "architecture": ARCHITECTURE,
        "steps": {case: step_results[case] for case in sorted(CASES)},
        "archives_present": {core_name: core_archive.is_file(),
                             extension_name: extension_archive.is_file()},
    }
    output.mkdir(parents=True, exist_ok=True)
    publication = output / "publication"
    publication.mkdir(parents=True, exist_ok=True)
    attempt_path = publication / "attempt.json"
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not core_archive.is_file() or not extension_archive.is_file():
        print("Archives are incomplete; retaining the raw attempt without a receipt or record.")
        return [attempt_path]

    digests = {core_name: sha256_file(core_archive), extension_name: sha256_file(extension_archive)}
    _sidecar(core_archive, digests[core_name])
    _sidecar(extension_archive, digests[extension_name])
    if digests[core_name] != selected["core_sha256"]:
        _fail("PostgreSQL core archive does not match the selected successful build")
    _archive_metadata(extension_archive, selected)
    attempt["archives"] = digests
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    reports_dir = output
    static_path = reports_dir / "static-analysis.json"
    symbols_path = reports_dir / "debug-symbols/index.json"
    diagnostics_path = reports_dir / "diagnostics.json"
    report_paths = {"static_analysis": static_path, "symbols": symbols_path,
                    "diagnostics": diagnostics_path}
    report_digests = {name: sha256_file(path) for name, path in report_paths.items() if path.is_file()}
    if results["archive-suite"] == "passed":
        static = _json(static_path, "static analysis")
        _archive_report(static, digests, "static analysis")
        if static.get("passed") is not True or not static.get("inspected_files"):
            _fail("static analysis did not pass over the assembled archive")
    if results["symbols"] == "passed":
        symbols = _json(symbols_path, "symbol")
        entries = symbols.get("files")
        if not isinstance(entries, list) or not entries:
            _fail("symbol index is empty")
        for entry in entries:
            name = entry.get("archive")
            if name not in digests or entry.get("archive_sha256") != digests[name]:
                _fail("symbol index is not bound to the final archive bytes")
        if not any(entry.get("archive") == extension_name
                   and entry.get("module_path") == "pgaudit/lib/pgaudit.dylib" for entry in entries):
            _fail("symbol index does not include the pgAudit module")
    if results["diagnostics"] == "passed":
        diagnostics = _json(diagnostics_path, "diagnostic")
        _archive_report(diagnostics, digests, "diagnostic")
        if (diagnostics.get("platform") != "macos"
                or diagnostics.get("architecture") != ARCHITECTURE
                or diagnostics.get("postgresql_version") != pg_version
                or diagnostics.get("pgaudit_version") != pgaudit_version
                or not isinstance(diagnostics.get("extension_load_failure"), dict)
                or not isinstance(diagnostics.get("postgresql_failure"), dict)):
            _fail("diagnostic report does not identify the expected failure investigations")
    receipt = {
        "schema_version": 1, "profile_id": profile_id,
        "profile_revision": profile["profile_revision"], "test_revision": revision,
        "project": "pgaudit", "version": pgaudit_version,
        "postgresql_version": pg_version, "architecture": ARCHITECTURE,
        "platform": PLATFORM, "endpoint": "current", "case_results": results,
        "archives": digests, "extension_archive": extension_name,
        "reports": report_digests,
        "clean_system": True,
        "dependency_check_profile": "macho-system-dependencies-v1",
        "dependency_checks_passed": (json.loads(static_path.read_text()).get("passed") is True
                                      if static_path.is_file() else False),
        "environment": {"os": "macos", "os_version": os_version,
                        "architecture": ARCHITECTURE, "image_id": image_id},
        "ci": {"provider": "github-actions", "run_id": run_id,
               "run_url": f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}",
               "source_revision": revision, "build_revision": revision,
               "test_revision": revision},
    }
    receipt_path = publication / "current-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = {
        "schema_version": 2, "scope": "publication", "profile_id": profile_id,
        "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
        "case_results": results, "test_revision": revision, "ci": receipt["ci"],
        "outcome": outcome, "sha256": digests[extension_name],
        "component": "pgaudit", "project": "pgaudit", "version": pgaudit_version,
        "platform": PLATFORM, "postgresql_version": pg_version,
        "assembled_core": {"archive": core_name, "sha256": digests[core_name],
                           "version": pg_version},
        "prerequisite_archives": [],
        "environment": {"os": "macos", "os_version": os_version,
                        "architecture": ARCHITECTURE, "clean_system": True,
                        "endpoint": "current", "image_id": image_id,
                        "dependency_check_profile": receipt["dependency_check_profile"],
                        "dependency_checks_passed": receipt["dependency_checks_passed"]},
    }
    support = coverage.load_json(root / "support.json")
    coverage.validate_verification_record(record, support, root)
    records_dir = publication / "records"
    records_dir.mkdir(parents=True, exist_ok=True)
    record_path = records_dir / f"pgaudit-{pgaudit_version}-postgresql-{pg_version}-{PLATFORM}-current-{run_id}.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(receipt_path)
    print(record_path)
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
    parser.add_argument("--symbols-result", required=True)
    parser.add_argument("--diagnostics-result", required=True)
    parser.add_argument("--postgresql-version", choices=("17.11", "18.6"), default="18.6")
    args = parser.parse_args()
    try:
        paths = emit(args.root, args.core_archives, args.archives, args.output,
                     {"archive-suite": args.archive_suite_result, "symbols": args.symbols_result,
                      "diagnostics": args.diagnostics_result}, args.os_version, args.image_id,
                     pg_version=args.postgresql_version)
        for path in paths:
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pgAudit macOS publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
