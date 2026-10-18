#!/usr/bin/env python3
"""Validate and retain one pgTAP Windows publication attempt."""

import argparse
import json
from pathlib import Path
import shutil
import sys

import coverage
import emit_pgtap_windows_publication as publication

MAX_EVIDENCE_BYTES = 1024 * 1024


def _read(path):
    value = coverage.load_json(path)
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"{path}: expected JSON object")
    return value


def _retain(source, destination, copies):
    source = Path(source)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
        raise coverage.CoverageError(f"evidence must be a regular file no larger than {MAX_EVIDENCE_BYTES} bytes: {source}")
    if destination.exists() and destination.read_bytes() != source.read_bytes():
        raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    copies.append((source, destination))


def _copy(copies):
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def import_run(root, core_artifact, pgtap_artifact, run_id, pg_version="18.6"):
    target = publication.target_for(pg_version)
    root, core_artifact, pgtap_artifact = map(Path, (root, core_artifact, pgtap_artifact))
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run_id must be numeric")
    support = coverage.load_json(root / "support.json")
    profile = coverage.verification_profile(root, target.profile_id)
    if (profile["scope"] != "publication" or profile["platforms"] != [publication.PLATFORM]
            or profile["case_ids"] != sorted(publication.CASES)):
        raise coverage.CoverageError("registered profile does not match the scoped pgTAP target")
    pub = pgtap_artifact / "publication"
    attempt_path = pub / "attempt.json"
    attempt = _read(attempt_path)
    if (attempt.get("schema_version") != 1 or str(attempt.get("run_id")) != run_id
            or attempt.get("profile_id") != target.profile_id
            or attempt.get("architecture") != publication.ARCHITECTURE
            or attempt.get("postgresql_version") != target.pg_version
            or attempt.get("pgtap_version") != publication.PGTAP_VERSION
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))):
        raise coverage.CoverageError("raw attempt identity does not match the requested run and profile")
    raw_steps = attempt.get("steps")
    if (not isinstance(raw_steps, dict) or set(raw_steps) != publication.CASES
            or any(value not in {"success", "failure", "skipped", "cancelled", "timed_out"}
                   for value in raw_steps.values())):
        raise coverage.CoverageError("raw attempt must retain each publication case outcome")
    results = {case: publication._step(value, case) for case, value in raw_steps.items()}
    evidence = root / "support/evidence" / f"pgtap-windows-publication-{run_id}" / publication.ARCHITECTURE
    copies = []
    _retain(attempt_path, evidence / "attempt.json", copies)
    core_name = f"postgresql-{target.pg_version}-{publication.PLATFORM}.tar.gz"
    extension_name = f"pgtap-{publication.PGTAP_VERSION}-postgresql-{target.pg_version}-{publication.PLATFORM}.tar.gz"
    core_archive, extension_archive = core_artifact / core_name, pgtap_artifact / extension_name
    receipt_path = pub / "current-receipt.json"
    record_paths = sorted((pub / "records").glob("*.json"))
    if not core_archive.is_file() or not extension_archive.is_file():
        if receipt_path.exists() or record_paths:
            raise coverage.CoverageError("archive-bound receipt or record exists without both archives")
        for name in ("static-analysis.json", "probe-output.txt", "prerequisite-output.txt"):
            source = pgtap_artifact / name
            if source.is_file():
                _retain(source, evidence / name, copies)
        _copy(copies)
        return [str(dest.relative_to(root)) for _, dest in copies]

    digests = {core_name: publication.sha256_file(core_archive),
               extension_name: publication.sha256_file(extension_archive)}
    for archive in (core_archive, extension_archive):
        publication._sidecar(archive, digests[archive.name])
    if digests[core_name] != target.core_sha256:
        raise coverage.CoverageError("core archive does not match the selected pinned PostgreSQL artifact")
    publication._metadata(extension_archive, target)
    if attempt.get("archives") != digests:
        raise coverage.CoverageError("raw attempt archive hashes differ from final archive bytes")
    if not receipt_path.is_file():
        raise coverage.CoverageError("complete archives require a publication receipt")
    receipt = _read(receipt_path)
    ci = receipt.get("ci")
    expected_receipt = {
        "schema_version": 1, "profile_id": target.profile_id,
        "profile_revision": profile["profile_revision"], "test_revision": attempt["source_revision"],
        "project": "pgtap", "version": publication.PGTAP_VERSION,
        "postgresql_version": target.pg_version, "architecture": publication.ARCHITECTURE,
        "platform": publication.PLATFORM, "endpoint": "current", "case_results": results,
        "archives": digests, "extension_archive": extension_name,
    }
    if any(receipt.get(key) != value for key, value in expected_receipt.items()):
        raise coverage.CoverageError("receipt identity or archive hashes differ from the raw attempt")
    if (not isinstance(ci, dict) or ci.get("provider") != "github-actions" or str(ci.get("run_id")) != run_id
            or any(ci.get(key) != attempt["source_revision"]
                   for key in ("source_revision", "build_revision", "test_revision"))
            or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")):
        raise coverage.CoverageError("receipt CI provenance differs from the raw attempt")
    if (receipt.get("clean_system") is not True
            or receipt.get("dependency_check_profile") != "windows-sql-archive-relocation-v1"
            or not isinstance(receipt.get("reports"), dict)
            or not isinstance(receipt.get("environment"), dict)
            or receipt["environment"].get("os") != "windows"
            or receipt["environment"].get("architecture") != publication.ARCHITECTURE
            or not receipt["environment"].get("os_version") or not receipt["environment"].get("image_id")):
        raise coverage.CoverageError("receipt environment or static-check profile is incomplete")
    report_sources = {"static_analysis": pgtap_artifact / "static-analysis.json",
                      "probe_output": pgtap_artifact / "probe-output.txt"}
    expected_reports = {}
    for key, source in report_sources.items():
        if source.is_file():
            expected_reports[key] = publication.sha256_file(source)
    if receipt["reports"] != expected_reports:
        raise coverage.CoverageError("receipt report hashes differ from the retained reports")
    static_path = pgtap_artifact / "static-analysis.json"
    if results["static-analysis"] == "passed":
        static = _read(static_path)
        if (static.get("passed") is not True or static.get("archives") != digests
                or static.get("native_extension_files") != [] or not static.get("inspected_files")):
            raise coverage.CoverageError("static-analysis report does not cover the final archives")
    if len(record_paths) != 1:
        raise coverage.CoverageError("expected exactly one pgTAP publication record")
    record_path = record_paths[0]
    record = _read(record_path)
    coverage.validate_verification_record(record, support, root)
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    expected_record = {
        "profile_id": target.profile_id, "component": "pgtap", "project": "pgtap",
        "version": publication.PGTAP_VERSION, "postgresql_version": target.pg_version,
        "platform": publication.PLATFORM, "case_results": results, "outcome": outcome,
        "test_cases": profile["case_ids"], "ci": ci, "test_revision": attempt["source_revision"],
        "sha256": digests[extension_name],
        "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": target.pg_version},
        "prerequisite_archives": [],
    }
    if (any(record.get(key) != value for key, value in expected_record.items())
            or record_path.name != f"pgtap-{publication.PGTAP_VERSION}-postgresql-{target.pg_version}-{publication.PLATFORM}-current-{run_id}.json"
            or record.get("environment", {}).get("clean_system") is not True
            or record.get("environment", {}).get("endpoint") != "current"
            or any(record.get("environment", {}).get(key) != receipt["environment"].get(key)
                   for key in ("os", "os_version", "architecture", "image_id"))
            or record.get("environment", {}).get("dependency_check_profile") != receipt["dependency_check_profile"]
            or record.get("environment", {}).get("dependency_checks_passed") != receipt.get("dependency_checks_passed")):
        raise coverage.CoverageError("record identity, archive or environment differs from receipt")
    for source in (receipt_path, static_path, pgtap_artifact / "probe-output.txt", record_path):
        if source.is_file():
            destination = (root / "support/verification" / source.name
                           if source == record_path else evidence / source.name)
            _retain(source, destination, copies)
    _copy(copies)
    return [str(dest.relative_to(root)) for _, dest in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True)
    parser.add_argument("--pgtap-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--postgresql-version", choices=publication.SUPPORTED_PG_VERSIONS, default="18.6")
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact, args.pgtap_artifact, args.run_id,
                                 args.postgresql_version)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pgTAP Windows publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
