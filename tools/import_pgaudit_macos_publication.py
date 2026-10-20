#!/usr/bin/env python3
"""Validate and retain one arm64 pgAudit macOS publication attempt."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import coverage
import emit_pgaudit_macos_publication as publication
from pgaudit_macos_targets import target


MAX_EVIDENCE_BYTES = 1024 * 1024
PROFILE_ID = target("18.6")["profile_id"]
CASES = publication.CASES


def _read(path):
    value = coverage.load_json(path)
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"{path}: expected JSON object")
    return value


def _retain(root, source, destination, copies):
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
        raise coverage.CoverageError(f"evidence must be a regular file no larger than {MAX_EVIDENCE_BYTES} bytes: {source}")
    if destination.exists() and destination.read_bytes() != source.read_bytes():
        raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    copies.append((source, destination))


def import_run(root, core_artifact, pgaudit_artifact, run_id, pg_version="18.6"):
    selected = target(pg_version)
    profile_id = selected["profile_id"]
    pgaudit_version = selected["pgaudit_version"]
    root, core_artifact, pgaudit_artifact = map(Path, (root, core_artifact, pgaudit_artifact))
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run_id must be numeric")
    support = coverage.load_json(root / "support.json")
    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or profile["platforms"] != [publication.PLATFORM]
            or profile["case_ids"] != sorted(CASES)):
        raise coverage.CoverageError("registered profile does not match the scoped pgAudit target")
    publication_dir = pgaudit_artifact / "publication"
    attempt_path = publication_dir / "attempt.json"
    attempt = _read(attempt_path)
    if (attempt.get("schema_version") != 1 or str(attempt.get("run_id")) != run_id
            or attempt.get("profile_id") != profile_id
            or attempt.get("architecture") != publication.ARCHITECTURE
            or attempt.get("postgresql_version") != pg_version
            or attempt.get("pgaudit_version") != pgaudit_version
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))):
        raise coverage.CoverageError("raw attempt identity does not match the requested run and profile")
    raw_steps = attempt.get("steps")
    if (not isinstance(raw_steps, dict) or set(raw_steps) != CASES
            or any(value not in {"success", "failure", "skipped", "cancelled", "timed_out"}
                   for value in raw_steps.values())):
        raise coverage.CoverageError("raw attempt must retain each publication case outcome")
    results = {case: publication._step_result(raw_steps[case], case) for case in sorted(CASES)}
    outcome = ("failed" if "failed" in results.values()
               else "skipped" if "skipped" in results.values() else "passed")
    evidence_dir = root / "support/evidence" / f"pgaudit-macos-publication-{run_id}" / publication.ARCHITECTURE
    copies = []
    _retain(root, attempt_path, evidence_dir / "attempt.json", copies)

    core_name = f"postgresql-{pg_version}-{publication.PLATFORM}.tar.gz"
    extension_name = f"pgaudit-{pgaudit_version}-postgresql-{pg_version}-{publication.PLATFORM}.tar.gz"
    core_archive, extension_archive = core_artifact / core_name, pgaudit_artifact / extension_name
    receipt_path = publication_dir / "current-receipt.json"
    record_paths = sorted((publication_dir / "records").glob("*.json"))
    if not core_archive.is_file() or not extension_archive.is_file():
        if receipt_path.exists() or record_paths:
            raise coverage.CoverageError("archive-bound receipt or record exists without both archives")
        for name in ("static-analysis.json", "diagnostics.json", "debug-symbols/index.json"):
            source = pgaudit_artifact / name
            if source.is_file():
                _retain(root, source, evidence_dir / name, copies)
        _copy(copies)
        return [str(destination.relative_to(root)) for _, destination in copies]

    digests = {core_name: publication.sha256_file(core_archive),
               extension_name: publication.sha256_file(extension_archive)}
    for archive in (core_archive, extension_archive):
        publication._sidecar(archive, digests[archive.name])
    if digests[core_name] != selected["core_sha256"]:
        raise coverage.CoverageError("core archive does not match the pinned PostgreSQL artifact")
    publication._archive_metadata(extension_archive, selected)

    if receipt_path.is_file():
        receipt = _read(receipt_path)
        ci = receipt.get("ci")
        expected = {
            "schema_version": 1, "profile_id": profile_id,
            "profile_revision": profile["profile_revision"],
            "test_revision": attempt["source_revision"],
            "project": "pgaudit", "version": pgaudit_version,
            "postgresql_version": pg_version,
            "architecture": publication.ARCHITECTURE, "platform": publication.PLATFORM,
            "endpoint": "current", "case_results": results, "archives": digests,
            "extension_archive": extension_name,
        }
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise coverage.CoverageError("receipt identity or archive hashes differ from the raw attempt")
        if (not isinstance(ci, dict) or ci.get("provider") != "github-actions"
                or str(ci.get("run_id")) != run_id
                or ci.get("source_revision") != attempt["source_revision"]
                or ci.get("build_revision") != attempt["source_revision"]
                or ci.get("test_revision") != attempt["source_revision"]
                or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")):
            raise coverage.CoverageError("receipt CI provenance differs from the raw attempt")
        if (not isinstance(receipt.get("reports"), dict)
                or receipt.get("dependency_check_profile") != "macho-system-dependencies-v1"
                or not isinstance(receipt.get("dependency_checks_passed"), bool)
                or receipt.get("clean_system") is not True):
            raise coverage.CoverageError("receipt environment or report digests are incomplete")
        report_paths = {
            "static_analysis": pgaudit_artifact / "static-analysis.json",
            "symbols": pgaudit_artifact / "debug-symbols/index.json",
            "diagnostics": pgaudit_artifact / "diagnostics.json",
        }
        report_results = {"static_analysis": "archive-suite", "symbols": "symbols",
                          "diagnostics": "diagnostics"}
        for name, source in report_paths.items():
            if source.is_file():
                if receipt["reports"].get(name) != publication.sha256_file(source):
                    raise coverage.CoverageError(f"receipt report hash does not match {name}")
            elif results[report_results[name]] == "passed":
                raise coverage.CoverageError(f"passing case is missing {name} report")
        static_path = report_paths["static_analysis"]
        if static_path.is_file() and results["archive-suite"] == "passed":
            static = _read(static_path)
            publication._archive_report(static, digests, "static analysis")
            if static.get("passed") is not True or not static.get("inspected_files"):
                raise coverage.CoverageError("passing static report is incomplete")
        symbols_path = report_paths["symbols"]
        if symbols_path.is_file() and results["symbols"] == "passed":
            entries = _read(symbols_path).get("files")
            if (not isinstance(entries, list)
                    or not any(item.get("archive") == extension_name
                               and item.get("archive_sha256") == digests[extension_name]
                               and item.get("module_path") == "pgaudit/lib/pgaudit.dylib"
                               for item in entries)):
                raise coverage.CoverageError("passing symbol index does not bind the pgAudit module")
        diagnostic_path = report_paths["diagnostics"]
        if diagnostic_path.is_file() and results["diagnostics"] == "passed":
            diagnostic = _read(diagnostic_path)
            publication._archive_report(diagnostic, digests, "diagnostic")
        if not record_paths and outcome == "passed":
            raise coverage.CoverageError("passing receipt has no verification record")
        for source in record_paths:
            record = _read(source)
            coverage.validate_verification_record(record, support, root)
            if (record.get("profile_id") != profile_id
                    or record.get("profile_revision") != profile["profile_revision"]
                    or record.get("case_results") != results or record.get("outcome") != outcome
                    or record.get("sha256") != digests[extension_name]
                    or record.get("assembled_core") != {
                        "archive": core_name, "sha256": digests[core_name],
                        "version": pg_version}
                    or record.get("ci") != ci
                    or record.get("environment", {}).get("image_id") != receipt.get("environment", {}).get("image_id")
                    or record.get("environment", {}).get("os_version") != receipt.get("environment", {}).get("os_version")
                    or record.get("environment", {}).get("dependency_checks_passed") != receipt.get("dependency_checks_passed")):
                raise coverage.CoverageError("verification record differs from receipt or archive bytes")
            _retain(root, source, root / "support/verification" / source.name, copies)
        _retain(root, receipt_path, evidence_dir / "current-receipt.json", copies)
    elif record_paths:
        raise coverage.CoverageError("verification records require their matching receipt")
    elif outcome == "passed":
        raise coverage.CoverageError("passing attempt has no archive-bound receipt")

    for name in ("static-analysis.json", "diagnostics.json", "debug-symbols/index.json"):
        source = pgaudit_artifact / name
        if source.is_file():
            _retain(root, source, evidence_dir / name, copies)
        elif outcome == "passed":
            raise coverage.CoverageError(f"passing run is missing {name}")
    _copy(copies)
    return [str(destination.relative_to(root)) for _, destination in copies]


def _copy(copies):
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True)
    parser.add_argument("--pgaudit-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--postgresql-version", choices=("17.11", "18.6"), default="18.6")
    args = parser.parse_args()
    try:
        for path in import_run(args.root, args.core_artifact, args.pgaudit_artifact, args.run_id,
                               args.postgresql_version):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"pgAudit macOS publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
