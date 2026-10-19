#!/usr/bin/env python3
"""Validate and retain one pg_cron macOS publication attempt."""

import argparse
from pathlib import Path
import re
import sys

import coverage
import emit_pgcron_macos_publication as publication
import macos_publication_evidence as evidence


MAX_EVIDENCE_BYTES = 1024 * 1024


def _read(path):
    return evidence.read_json_object(path, MAX_EVIDENCE_BYTES)


def _retain(source, destination, copies):
    evidence.retain(source, destination, copies, MAX_EVIDENCE_BYTES)


def _copy(copies):
    evidence.copy_retained(copies, MAX_EVIDENCE_BYTES)


def import_run(root, core_artifact, extension_artifact, run_id, target_config=None):
    root, core_artifact, extension_artifact = map(Path, (root, core_artifact, extension_artifact))
    target = publication.target_info(target_config)
    PG_VERSION, VERSION = target["pg_version"], target["version"]
    ARCHITECTURE, PLATFORM = target["architecture"], target["platform"]
    PROFILE_ID, CORE_SHA256 = target["profile_id"], target["core_sha256"]
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run_id must be numeric")
    support = coverage.load_json(root / "support.json")
    profile = coverage.verification_profile(root, PROFILE_ID)
    if (profile["scope"] != "publication" or profile["platforms"] != [PLATFORM]
            or profile["case_ids"] != sorted(publication.CASES)):
        raise coverage.CoverageError("registered profile does not match scoped pg_cron target")

    publication_dir = extension_artifact / "publication"
    attempt_path = publication_dir / "attempt.json"
    attempt = _read(attempt_path)
    if (attempt.get("schema_version") != 1 or str(attempt.get("run_id")) != run_id
            or attempt.get("profile_id") != PROFILE_ID
            or attempt.get("architecture") != ARCHITECTURE
            or attempt.get("postgresql_version") != PG_VERSION
            or attempt.get("pg_cron_version") != VERSION
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))):
        raise coverage.CoverageError("raw attempt identity does not match requested run and profile")
    raw_steps = attempt.get("steps")
    allowed = {"success", "failure", "skipped", "cancelled", "timed_out"}
    if (not isinstance(raw_steps, dict) or set(raw_steps) != publication.CASES
            or any(value not in allowed for value in raw_steps.values())):
        raise coverage.CoverageError("raw attempt must retain each publication case outcome")
    results = {case: publication._step_result(raw_steps[case], case)
               for case in sorted(publication.CASES)}
    outcome = ("failed" if "failed" in results.values()
               else "skipped" if "skipped" in results.values() else "passed")
    evidence_dir = root / "support/evidence" / f"pgcron-macos-publication-{run_id}" / ARCHITECTURE
    copies = []
    _retain(attempt_path, evidence_dir / "attempt.json", copies)

    core_name = f"postgresql-{PG_VERSION}-{PLATFORM}.tar.gz"
    extension_name = f"pg_cron-{VERSION}-postgresql-{PG_VERSION}-{PLATFORM}.tar.gz"
    core_archive, extension_archive = core_artifact / core_name, extension_artifact / extension_name
    receipt_path = publication_dir / "current-receipt.json"
    records = sorted((publication_dir / "records").glob("*.json"))
    report_paths = {key: extension_artifact / filename
                    for key, filename in publication.REPORTS.items()}
    if not core_archive.is_file() or not extension_archive.is_file():
        if receipt_path.exists() or records:
            raise coverage.CoverageError("archive-bound receipt or record exists without both archives")
        for source in report_paths.values():
            if source.is_file():
                _retain(source, evidence_dir / source.name, copies)
        _copy(copies)
        return [str(destination.relative_to(root)) for _, destination in copies]

    digests = {core_name: publication.sha256_file(core_archive),
               extension_name: publication.sha256_file(extension_archive)}
    for archive in (core_archive, extension_archive):
        publication._sidecar(archive, digests[archive.name])
    if digests[core_name] != CORE_SHA256:
        raise coverage.CoverageError("core archive does not match pinned PostgreSQL 18.6 artifact")
    publication._metadata(extension_archive, target)
    try:
        components, native_files = publication.check_archive(extension_archive)
    except (OSError, ValueError) as exc:
        raise coverage.CoverageError(f"final archive licence inventory is invalid: {exc}") from exc
    if components != 1 or native_files != 1:
        raise coverage.CoverageError("final archive does not inventory one native payload and its licence")
    if attempt.get("archives") != digests:
        raise coverage.CoverageError("raw attempt archive hashes differ from final archive bytes")

    if receipt_path.is_file():
        receipt = _read(receipt_path)
        expected_receipt = {
            "schema_version": 1, "profile_id": PROFILE_ID,
            "profile_revision": profile["profile_revision"],
            "test_revision": attempt["source_revision"],
            "project": "pg_cron", "version": VERSION,
            "postgresql_version": PG_VERSION,
            "architecture": ARCHITECTURE, "platform": PLATFORM,
            "endpoint": "current", "case_results": results, "archives": digests,
            "extension_archive": extension_name,
        }
        if any(receipt.get(key) != value for key, value in expected_receipt.items()):
            raise coverage.CoverageError("receipt identity or archive hashes differ from raw attempt")
        environment = receipt.get("environment")
        ci = receipt.get("ci")
        if (receipt.get("clean_system") is not True
                or receipt.get("dependency_check_profile") != "macho-system-dependencies-v1"
                or receipt.get("dependency_checks_passed") is not (results["static-analysis"] == "passed")
                or not isinstance(environment, dict) or environment.get("os") != "macos"
                or environment.get("architecture") != ARCHITECTURE
                or not re.fullmatch(r"\d+(?:\.\d+)*", str(environment.get("os_version", "")))
                or not environment.get("image_id") or not isinstance(ci, dict)
                or ci.get("provider") != "github-actions" or str(ci.get("run_id")) != run_id
                or any(ci.get(key) != attempt["source_revision"]
                       for key in ("source_revision", "build_revision", "test_revision"))
                or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")):
            raise coverage.CoverageError("receipt environment or CI provenance is incomplete")
        report_digests = receipt.get("reports")
        if not isinstance(report_digests, dict):
            raise coverage.CoverageError("receipt report digests are missing")
        for key, source in report_paths.items():
            if source.is_file():
                if report_digests.get(key) != publication.sha256_file(source):
                    raise coverage.CoverageError(f"receipt digest differs for {key}")
            elif results["archive-suite" if key == "probe_output" else "static-analysis"] == "passed":
                raise coverage.CoverageError(f"passing receipt is missing {key}")
        if results["static-analysis"] == "passed":
            publication._check_static(report_paths["static_analysis"],
                                      report_paths["macho_inspection"], digests, ARCHITECTURE)
        if results["archive-suite"] == "passed":
            publication._check_probe(report_paths["probe_output"])
        _retain(receipt_path, evidence_dir / receipt_path.name, copies)
    elif records:
        raise coverage.CoverageError("verification records require a matching receipt")

    if len(records) > 1:
        raise coverage.CoverageError("expected one pg_cron verification record")
    if receipt_path.is_file() and not records:
        raise coverage.CoverageError("receipt exists without verification record")
    for source in records:
        record = _read(source)
        coverage.validate_verification_record(record, support, root)
        expected_record = {
            "profile_id": PROFILE_ID, "component": "pg_cron",
            "project": "pg_cron", "version": VERSION,
            "postgresql_version": PG_VERSION, "platform": PLATFORM,
            "case_results": results, "outcome": outcome, "test_cases": profile["case_ids"],
            "ci": receipt["ci"], "test_revision": receipt["test_revision"],
            "sha256": digests[extension_name],
            "assembled_core": {"archive": core_name, "sha256": digests[core_name],
                               "version": PG_VERSION},
            "prerequisite_archives": [],
        }
        if (any(record.get(key) != value for key, value in expected_record.items())
                or source.name != f"pg_cron-{VERSION}-postgresql-{PG_VERSION}-{PLATFORM}-current-{run_id}.json"
                or any(record.get("environment", {}).get(key) != receipt["environment"].get(key)
                       for key in ("os", "os_version", "architecture", "image_id"))
                or record.get("environment", {}).get("clean_system") is not True
                or record.get("environment", {}).get("endpoint") != "current"
                or record.get("environment", {}).get("dependency_check_profile")
                   != receipt["dependency_check_profile"]
                or record.get("environment", {}).get("dependency_checks_passed")
                   != receipt["dependency_checks_passed"]):
            raise coverage.CoverageError("verification record differs from receipt or archive bytes")
        _retain(source, root / "support/verification" / source.name, copies)
    for source in report_paths.values():
        if source.is_file():
            _retain(source, evidence_dir / source.name, copies)
    _copy(copies)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True)
    parser.add_argument("--extension-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-config", type=Path)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact,
                                   args.extension_artifact, args.run_id,
                                   target_config=args.target_config)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_cron macOS publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
