#!/usr/bin/env python3
"""Bind a pg_cron macOS archive and its checks into publication evidence."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import coverage
import macos_publication_evidence as evidence
from check_macos_extension_license_inventory import check_archive
from scripts.pg_cron.macos_target import load_target


PG_VERSION = "18.6"
VERSION = "1.6.8"
ARCHITECTURE = os.environ.get("PGCRON_MACOS_ARCHITECTURE", "arm64")
if ARCHITECTURE not in {"arm64", "x86_64"}:
    raise ValueError("PGCRON_MACOS_ARCHITECTURE must be arm64 or x86_64")
PROFILE_ID = f"pgcron-publication-macos-{ARCHITECTURE}-18.6"
PLATFORM = f"macos-{ARCHITECTURE}"
CORE_SHA256 = {
    "arm64": "bc543b0d54a8a33b3b737eab74d7f185035f01e5c2db4eb48be049996eee4440",
    "x86_64": "5ec45e48bad1439860f0143fd6f2cbc04a86cfa456beef8c5ca9040960ea3f40",
}[ARCHITECTURE]
SOURCE_URL = "https://github.com/citusdata/pg_cron/archive/refs/tags/v1.6.8.tar.gz"
SOURCE_SHA256 = "c19ab9bb35406c60fb51ecda993737c083850abe424acb6c1030439d00a1f8e4"
CASES = {"archive-suite", "static-analysis"}
REPORTS = {"static_analysis": "static-analysis.json",
           "macho_inspection": "pg-cron-macho-inspection.json",
           "probe_output": "probe-output.txt"}


def target_info(target_config=None):
    if target_config is None:
        return {"pg_version": PG_VERSION, "version": VERSION,
                "architecture": ARCHITECTURE, "platform": PLATFORM,
                "profile_id": PROFILE_ID, "core_sha256": CORE_SHA256,
                "source_url": SOURCE_URL, "source_sha256": SOURCE_SHA256}
    value = load_target(target_config, require_resolved=True)
    return {"pg_version": value["postgresql_version"], "version": value["pg_cron_version"],
            "architecture": value["architecture"], "platform": value["platform"],
            "profile_id": value["profile_id"], "core_sha256": value["core_sha256"],
            "source_url": value["source_url"], "source_sha256": value["source_sha256"]}


def _fail(message):
    raise coverage.CoverageError(message)


def sha256_file(path):
    return evidence.sha256_file(path)


def _sidecar(path, digest):
    evidence.check_sidecar(path, digest, "missing checksum sidecar for {name}")


def _metadata(path, target):
    try:
        with tarfile.open(path, "r:gz") as archive:
            member = next((item for item in archive.getmembers()
                           if item.name == "metadata.json" and item.isfile()
                           and item.size <= 1024 * 1024), None)
            if member is None:
                _fail("pg_cron archive requires bounded metadata.json")
            value = json.loads(archive.extractfile(member).read().decode("utf-8"))
            control = next((item for item in archive.getmembers()
                            if item.name == "pg_cron/share/extension/pg_cron.control"
                            and item.isfile() and item.size <= 64 * 1024), None)
            if control is None:
                _fail("pg_cron archive requires its pg_cron.control file")
            control_text = archive.extractfile(control).read().decode("utf-8")
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read pg_cron archive metadata: {exc}")
    core_name = f"postgresql-{target['pg_version']}-{target['platform']}.tar.gz"
    expected = {
        "project": "pg_cron", "version": target["version"], "sql_names": ["pg_cron"],
        "requires": [],
        "configuration_prerequisites": [
            {"type": "postgresql_setting", "name": "shared_preload_libraries", "value": "pg_cron"},
            {"type": "postgresql_setting", "name": "cron.use_background_workers", "value": "on"},
        ],
        "runtime_prerequisites": [], "postgresql_version": target["pg_version"],
        "platform": "macos", "architecture": target["architecture"],
        "source": {"url": target["source_url"], "sha256": target["source_sha256"]},
        "core_archive": {"basename": core_name, "sha256": target["core_sha256"]},
    }
    if not isinstance(value, dict) or value != expected:
        _fail("pg_cron metadata does not match the pinned publication target")
    if not re.search(r"(?m)^default_version\s*=\s*'1\.6'\s*$", control_text):
        _fail("pg_cron.control does not declare the expected SQL extension version")


def _json(path, label):
    try:
        return evidence.read_json_object(path)
    except coverage.CoverageError:
        _fail(f"{label} report is missing or invalid")


def _step_result(value, name):
    mapping = {"success": "passed", "failure": "failed", "skipped": "skipped",
               "cancelled": "skipped", "timed_out": "failed"}
    if value not in mapping:
        _fail(f"{name} result must be a GitHub Actions step outcome")
    return mapping[value]


def _check_probe(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        _fail("passing archive suite is missing pg_cron probe output")
    rows = re.search(r"(?m)^scheduled_job_rows=(\d+)\s*$", text)
    required = ("CREATE EXTENSION", "installation_relocated=true",
                "job_execution_mode=background_worker", "scheduled_job_status=succeeded")
    if (any(value not in text for value in required) or rows is None
            or int(rows.group(1)) < 1 or "unschedule" not in text.lower()):
        _fail("pg_cron output does not prove relocation and a completed background-worker job")


def _archive_map(report):
    value = report.get("archives")
    if isinstance(value, list):
        try:
            value = {item["basename"]: item["sha256"] for item in value}
        except (KeyError, TypeError):
            value = None
    return value


def _check_static(path, macho_path, digests, architecture):
    static = _json(path, "static analysis")
    if (_archive_map(static) != digests or static.get("passed") is not True
            or static.get("architecture") != architecture
            or not static.get("inspected_files") or static.get("findings")):
        _fail("core Mach-O analysis did not pass against the final archive bytes")
    macho = _json(macho_path, "pg_cron Mach-O inspection")
    if (macho.get("archives") != digests or macho.get("passed") is not True
            or macho.get("architecture") != architecture
            or macho.get("file") != "lib/pg_cron.dylib"
            or macho.get("minimum_os") != "11.0" or macho.get("findings")):
        _fail("pg_cron Mach-O inspection did not pass against the final archive bytes")
    dependencies = macho.get("dependencies")
    if (not isinstance(dependencies, dict)
            or dependencies.get("@rpath/libpq.5.dylib") != "lib/libpq.5.dylib"
            or "@loader_path" not in macho.get("module_rpaths", [])):
        _fail("pg_cron Mach-O report does not resolve bundled libpq through its module run path")


def emit(root, core_dir, archives, output, step_results, os_version, image_id,
         environ=None, target_config=None):
    root, core_dir, archives, output = map(Path, (root, core_dir, archives, output))
    target = target_info(target_config)
    PG_VERSION, VERSION = target["pg_version"], target["version"]
    ARCHITECTURE, PLATFORM = target["architecture"], target["platform"]
    PROFILE_ID, CORE_SHA256 = target["profile_id"], target["core_sha256"]
    environ = os.environ if environ is None else environ
    if not isinstance(step_results, dict) or set(step_results) != CASES:
        _fail("step_results must identify archive-suite and static-analysis")
    results = {case: _step_result(step_results[case], case) for case in sorted(CASES)}
    outcome = ("failed" if "failed" in results.values()
               else "skipped" if "skipped" in results.values() else "passed")
    revision, run_id = environ.get("GITHUB_SHA", ""), environ.get("GITHUB_RUN_ID", "")
    repository, server_url = environ.get("GITHUB_REPOSITORY", ""), environ.get("GITHUB_SERVER_URL", "")
    if (not coverage.REVISION.fullmatch(revision) or not run_id.isdigit()
            or not repository or not server_url):
        _fail("GitHub Actions revision and run provenance are required")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version or "") or not image_id:
        _fail("macOS runner version and image identifier are required")
    profile = coverage.verification_profile(root, PROFILE_ID)
    if (profile["scope"] != "publication" or profile["platforms"] != [PLATFORM]
            or profile["case_ids"] != sorted(CASES) or not profile["sources_available"]):
        _fail("registered profile does not match this pg_cron publication suite")

    core_name = f"postgresql-{PG_VERSION}-{PLATFORM}.tar.gz"
    extension_name = f"pg_cron-{VERSION}-postgresql-{PG_VERSION}-{PLATFORM}.tar.gz"
    core_archive, extension_archive = core_dir / core_name, archives / extension_name
    publication_dir = output / "publication"
    publication_dir.mkdir(parents=True, exist_ok=True)
    attempt_path = publication_dir / "attempt.json"
    attempt = {
        "schema_version": 1, "run_id": run_id, "source_revision": revision,
        "profile_id": PROFILE_ID, "postgresql_version": PG_VERSION,
        "pg_cron_version": VERSION, "architecture": ARCHITECTURE,
        "steps": {case: step_results[case] for case in sorted(CASES)},
        "archives_present": {core_name: core_archive.is_file(),
                             extension_name: extension_archive.is_file()},
    }
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not core_archive.is_file() or not extension_archive.is_file():
        return [attempt_path]

    digests = {core_name: sha256_file(core_archive), extension_name: sha256_file(extension_archive)}
    _sidecar(core_archive, digests[core_name])
    _sidecar(extension_archive, digests[extension_name])
    if digests[core_name] != CORE_SHA256:
        _fail("PostgreSQL core archive does not match the pinned pilot run")
    _metadata(extension_archive, target)
    try:
        components, native_files = check_archive(extension_archive)
    except (OSError, ValueError) as exc:
        _fail(f"final pg_cron archive licence inventory is invalid: {exc}")
    if components != 1 or native_files != 1:
        _fail("final pg_cron archive must inventory its native payload and licence")
    attempt["archives"] = digests
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    paths = {key: output / filename for key, filename in REPORTS.items()}
    report_digests = {key: sha256_file(path) for key, path in paths.items() if path.is_file()}
    if results["archive-suite"] == "passed":
        _check_probe(paths["probe_output"])
    if results["static-analysis"] == "passed":
        _check_static(paths["static_analysis"], paths["macho_inspection"], digests,
                      ARCHITECTURE)

    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    receipt = {
        "schema_version": 1, "profile_id": PROFILE_ID,
        "profile_revision": profile["profile_revision"], "test_revision": revision,
        "project": "pg_cron", "version": VERSION, "postgresql_version": PG_VERSION,
        "architecture": ARCHITECTURE, "platform": PLATFORM, "endpoint": "current",
        "case_results": results, "archives": digests,
        "extension_archive": extension_name, "reports": report_digests,
        "clean_system": True, "dependency_check_profile": "macho-system-dependencies-v1",
        "dependency_checks_passed": (results["static-analysis"] == "passed"),
        "environment": {"os": "macos", "os_version": os_version,
                        "architecture": ARCHITECTURE, "image_id": image_id},
        "ci": ci,
    }
    receipt_path = publication_dir / "current-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = {
        "schema_version": 2, "scope": "publication", "profile_id": PROFILE_ID,
        "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
        "case_results": results, "test_revision": revision, "ci": ci,
        "outcome": outcome, "sha256": digests[extension_name],
        "component": "pg_cron", "project": "pg_cron", "version": VERSION,
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
    records = publication_dir / "records"
    records.mkdir(parents=True, exist_ok=True)
    record_path = records / f"pg_cron-{VERSION}-postgresql-{PG_VERSION}-{PLATFORM}-current-{run_id}.json"
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
    parser.add_argument("--target-config", type=Path)
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.core_archives, args.archives, args.output,
                         {"archive-suite": args.archive_suite_result,
                          "static-analysis": args.static_analysis_result},
                         args.os_version, args.image_id, target_config=args.target_config):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_cron macOS publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
