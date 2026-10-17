#!/usr/bin/env python3
"""Validate and retain one pgTAP macOS arm64 publication attempt."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import coverage
import emit_pgtap_macos_publication as publication


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


def import_run(root, core_artifact, pgtap_artifact, run_id):
    root, core_artifact, pgtap_artifact = map(Path, (root, core_artifact, pgtap_artifact))
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run_id must be numeric")
    support = coverage.load_json(root / "support.json")
    profile = coverage.verification_profile(root, publication.PROFILE_ID)
    if (profile["scope"] != "publication" or profile["platforms"] != [publication.PLATFORM]
            or profile["case_ids"] != sorted(publication.CASES)):
        raise coverage.CoverageError("registered profile does not match the scoped pgTAP target")
    publication_dir = pgtap_artifact / "publication"
    attempt_path = publication_dir / "attempt.json"
    attempt = _read(attempt_path)
    if (attempt.get("schema_version") != 1 or str(attempt.get("run_id")) != run_id
            or attempt.get("profile_id") != publication.PROFILE_ID
            or attempt.get("architecture") != publication.ARCHITECTURE
            or attempt.get("postgresql_version") != publication.PG_VERSION
            or attempt.get("pgtap_version") != publication.PGTAP_VERSION
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))):
        raise coverage.CoverageError("raw attempt identity does not match the requested run and profile")
    raw_steps = attempt.get("steps")
    if (not isinstance(raw_steps, dict) or set(raw_steps) != publication.CASES
            or any(value not in {"success", "failure", "skipped", "cancelled", "timed_out"}
                   for value in raw_steps.values())):
        raise coverage.CoverageError("raw attempt must retain each publication case outcome")
    results = {case: publication._step_result(raw_steps[case], case) for case in sorted(publication.CASES)}
    target = root / "support/evidence" / f"pgtap-macos-publication-{run_id}" / publication.ARCHITECTURE
    copies = []
    _retain(attempt_path, target / "attempt.json", copies)

    core_name = f"postgresql-{publication.PG_VERSION}-{publication.PLATFORM}.tar.gz"
    extension_name = f"pgtap-{publication.PGTAP_VERSION}-postgresql-{publication.PG_VERSION}-{publication.PLATFORM}.tar.gz"
    core_archive, extension_archive = core_artifact / core_name, pgtap_artifact / extension_name
    receipt_path = publication_dir / "current-receipt.json"
    records = sorted((publication_dir / "records").glob("*.json"))
    if not core_archive.is_file() or not extension_archive.is_file():
        if receipt_path.exists() or records:
            raise coverage.CoverageError("archive-bound receipt or record exists without both archives")
        for name in ("static-analysis.json", "probe-output.txt", "build-log.txt"):
            source = pgtap_artifact / name
            if source.is_file():
                _retain(source, target / name, copies)
        _copy(copies)
        return [str(destination.relative_to(root)) for _, destination in copies]

    digests = {core_name: publication.sha256_file(core_archive),
               extension_name: publication.sha256_file(extension_archive)}
    for archive in (core_archive, extension_archive):
        publication._sidecar(archive, digests[archive.name])
    if digests[core_name] != publication.CORE_SHA256:
        raise coverage.CoverageError("core archive does not match the pinned PostgreSQL 18.6 artifact")
    publication._archive_metadata(extension_archive)
    if attempt.get("archives") != digests:
        raise coverage.CoverageError("raw attempt archive hashes differ from final archive bytes")

    if receipt_path.is_file():
        receipt = _read(receipt_path)
        ci = receipt.get("ci")
        expected = {
            "schema_version": 1, "profile_id": publication.PROFILE_ID,
            "profile_revision": profile["profile_revision"], "test_revision": attempt["source_revision"],
            "project": "pgtap", "version": publication.PGTAP_VERSION,
            "postgresql_version": publication.PG_VERSION,
            "architecture": publication.ARCHITECTURE, "platform": publication.PLATFORM,
            "endpoint": "current", "case_results": results, "archives": digests,
            "extension_archive": extension_name,
        }
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise coverage.CoverageError("receipt identity or archive hashes differ from the raw attempt")
        if (not isinstance(ci, dict) or ci.get("provider") != "github-actions"
                or str(ci.get("run_id")) != run_id
                or any(ci.get(key) != attempt["source_revision"]
                       for key in ("source_revision", "build_revision", "test_revision"))
                or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")):
            raise coverage.CoverageError("receipt CI provenance differs from the raw attempt")
        if (receipt.get("clean_system") is not True
                or receipt.get("dependency_check_profile") != "macho-system-dependencies-v1"
                or not isinstance(receipt.get("dependency_checks_passed"), bool)
                or not isinstance(receipt.get("reports"), dict)
                or not isinstance(receipt.get("environment"), dict)
                or receipt.get("environment", {}).get("os") != "macos"
                or receipt.get("environment", {}).get("architecture") != publication.ARCHITECTURE
                or not re.fullmatch(r"\d+(?:\.\d+)*", str(receipt.get("environment", {}).get("os_version", "")))
                or not receipt.get("environment", {}).get("image_id")):
            raise coverage.CoverageError("receipt environment or report digests are incomplete")
        report_sources = {"static_analysis": pgtap_artifact / "static-analysis.json",
                          "probe_output": pgtap_artifact / "probe-output.txt",
                          "build_log": pgtap_artifact / "build-log.txt"}
        for key, source in report_sources.items():
            if source.is_file():
                if receipt["reports"].get(key) != publication.sha256_file(source):
                    raise coverage.CoverageError(f"receipt digest does not match retained {key}")
            elif key in receipt["reports"]:
                raise coverage.CoverageError(f"receipt names missing {key} report")
        if results["static-analysis"] == "passed":
            static = _read(report_sources["static_analysis"])
            publication._report_archives(static, digests, "static analysis")
            if (static.get("passed") is not True
                    or static.get("architecture") != publication.ARCHITECTURE
                    or not static.get("inspected_files")):
                raise coverage.CoverageError("static-analysis case lacks a passing report")
        _retain(receipt_path, target / "current-receipt.json", copies)
    elif records:
        raise coverage.CoverageError("verification records require a matching receipt")

    if len(records) > 1:
        raise coverage.CoverageError("expected one pgTAP verification record")
    if receipt_path.is_file() and not records:
        raise coverage.CoverageError("receipt exists without its verification record")
    for source in records:
        record = _read(source)
        coverage.validate_verification_record(record, support, root)
        expected = {
            "profile_id": publication.PROFILE_ID, "component": "pgtap", "project": "pgtap",
            "version": publication.PGTAP_VERSION, "postgresql_version": publication.PG_VERSION,
            "platform": publication.PLATFORM, "case_results": results,
            "outcome": ("failed" if "failed" in results.values() else
                        "skipped" if "skipped" in results.values() else "passed"),
            "test_cases": profile["case_ids"], "ci": receipt["ci"],
            "test_revision": receipt["test_revision"], "sha256": digests[extension_name],
            "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": publication.PG_VERSION},
            "prerequisite_archives": [],
        }
        if (any(record.get(key) != value for key, value in expected.items())
                or source.name != f"pgtap-{publication.PGTAP_VERSION}-postgresql-{publication.PG_VERSION}-{publication.PLATFORM}-current-{run_id}.json"
                or any(record.get("environment", {}).get(key) != receipt.get("environment", {}).get(key)
                       for key in ("os", "os_version", "architecture", "image_id"))
                or record.get("environment", {}).get("clean_system") != receipt.get("clean_system")
                or record.get("environment", {}).get("endpoint") != receipt.get("endpoint")
                or record.get("environment", {}).get("dependency_check_profile") != receipt.get("dependency_check_profile")
                or record.get("environment", {}).get("dependency_checks_passed") != receipt.get("dependency_checks_passed")):
            raise coverage.CoverageError("record identity, archive or environment differs from receipt")
        copies.append((source, root / "support/verification" / source.name))
    for name in ("static-analysis.json", "probe-output.txt", "build-log.txt"):
        source = pgtap_artifact / name
        if source.is_file():
            _retain(source, target / name, copies)
    _copy(copies)
    return [str(destination.relative_to(root)) for _, destination in copies]


def _copy(copies):
    for source, destination in copies:
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise coverage.CoverageError(f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {source}")
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True)
    parser.add_argument("--pgtap-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact, args.pgtap_artifact, args.run_id)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pgTAP macOS publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
