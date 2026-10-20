#!/usr/bin/env python3
"""Validate and retain one selected Address Standardizer macOS attempt."""

import argparse
from pathlib import Path
import re
import sys

import coverage
import extension_archive_plan
import macos_publication_evidence as evidence

VERSION = "3.7.0"
BLOCK = "pending-dependency-provenance-and-redistribution-review"
CASES = {"archive-suite", "macho-closure"}
OUTCOMES = {"success", "failure", "skipped", "cancelled", "timed_out"}
REPORTS = {"static_analysis": "static-analysis.json", "probe_output": "probe-output.txt"}


def _read(path):
    return evidence.read_json_object(path)


def _step(value):
    if value not in OUTCOMES:
        raise coverage.CoverageError("attempt has an invalid workflow step outcome")
    return "passed" if value == "success" else "failed" if value in {"failure", "timed_out"} else "skipped"


def _copy(copies):
    evidence.copy_retained(copies)


def import_run(root, core_dir, archive_dir, run_id, target_path):
    root, core_dir, archive_dir = map(Path, (root, core_dir, archive_dir))
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run_id must be numeric")
    target = _read(target_path)
    pg, architecture = target.get("postgresql_version"), target.get("architecture")
    platform, profile_id = target.get("platform"), target.get("profile_id")
    if (not re.fullmatch(r"\d+\.\d+", str(pg)) or architecture not in {"arm64", "x86_64"}
            or platform != f"macos-{architecture}"
            or profile_id != f"address-standardizer-publication-macos-{architecture}-{pg}"):
        raise coverage.CoverageError("selected target identity is invalid")
    support = coverage.load_json(root / "support.json")
    releases = coverage.load_json(root / "support/postgresql-releases.json")
    extension_archive_plan.select_target(
        extension_archive_plan.plan(support, releases), "Address Standardizer", platform, pg, VERSION)
    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or profile["platforms"] != [platform]
            or set(profile["case_ids"]) != CASES):
        raise coverage.CoverageError("registered publication profile does not match target")

    publication = archive_dir / "publication"
    attempt_path = publication / "attempt.json"
    attempt = _read(attempt_path)
    if (attempt.get("schema_version") != 1 or str(attempt.get("run_id")) != run_id
            or attempt.get("source_revision") is None
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision")))
            or attempt.get("profile_id") != profile_id
            or attempt.get("postgresql_version") != pg
            or attempt.get("version") != VERSION
            or attempt.get("architecture") != architecture
            or attempt.get("release_eligible") is not False
            or attempt.get("redistribution_status") != BLOCK):
        raise coverage.CoverageError("attempt identity does not match selected run and target")
    raw_steps = attempt.get("steps")
    if not isinstance(raw_steps, dict) or set(raw_steps) != CASES:
        raise coverage.CoverageError("attempt must retain both publication case outcomes")
    results = {case: _step(raw_steps[case]) for case in sorted(CASES)}
    core_name = f"postgresql-{pg}-{platform}.tar.gz"
    extension_name = f"address-standardizer-{VERSION}-postgresql-{pg}-{platform}.tar.gz"
    core, extension = core_dir / core_name, archive_dir / extension_name
    present = {core_name: core.is_file(), extension_name: extension.is_file()}
    if attempt.get("archives_present") != present:
        raise coverage.CoverageError("attempt archive-presence map differs from downloaded files")

    evidence_dir = root / "support/evidence" / f"address-standardizer-macos-publication-{run_id}" / architecture
    copies = []
    evidence.retain(attempt_path, evidence_dir / "attempt.json", copies)
    for key, filename in REPORTS.items():
        source = archive_dir / filename
        if source.is_file():
            evidence.retain(source, evidence_dir / filename, copies)
    _copy(copies)

    receipt_path = publication / "current-receipt.json"
    record_path = publication / "verification-record.json"
    record_destination = root / "support/verification" / (
        f"address-standardizer-{VERSION}-postgresql-{pg}-{platform}-current-{run_id}.json")
    if not all(present.values()):
        if receipt_path.exists() or record_path.exists():
            raise coverage.CoverageError("archive-bound receipt or record exists without both archives")
        _copy(copies)
        return [str(destination.relative_to(root)) for _, destination in copies]

    for archive in (core, extension):
        if archive.is_symlink():
            raise coverage.CoverageError("publication archives must not be symbolic links")
    digests = {core_name: evidence.sha256_file(core), extension_name: evidence.sha256_file(extension)}
    for archive in (core, extension):
        evidence.check_sidecar(archive, digests[archive.name], "missing checksum sidecar for {name}")
    if attempt.get("archives") != digests:
        raise coverage.CoverageError("attempt archive hashes differ from final archive bytes")

    import json
    import tarfile
    try:
        with tarfile.open(extension, "r:gz") as tar:
            member = tar.getmember("metadata.json")
            if not member.isfile() or member.size > evidence.MAX_EVIDENCE_BYTES:
                raise coverage.CoverageError("extension archive metadata is missing or oversized")
            metadata = json.load(tar.extractfile(member))
    except (OSError, tarfile.TarError, KeyError, ValueError) as exc:
        raise coverage.CoverageError(f"cannot read extension archive metadata: {exc}") from exc
    if not isinstance(metadata, dict):
        raise coverage.CoverageError("extension archive metadata must be a JSON object")
    expected_metadata = {
        "project": "Address Standardizer", "version": VERSION,
        "sql_names": ["address_standardizer", "address_standardizer_data_us"],
        "postgresql_version": pg, "platform": "macos", "architecture": architecture,
        "core_archive": {"basename": core_name, "sha256": digests[core_name]},
    }
    if any(metadata.get(key) != value for key, value in expected_metadata.items()):
        raise coverage.CoverageError("extension metadata does not bind selected core and target")
    if not receipt_path.is_file() and not record_path.is_file():
        if attempt.get("archives") != digests:
            raise coverage.CoverageError("attempt archive hashes differ from final archive bytes")
        for archive in (core, extension):
            sidecar = Path(str(archive) + ".sha256")
            if sidecar.is_file():
                evidence.check_sidecar(archive, digests[archive.name], "checksum sidecar is invalid for {name}")
        _copy(copies)
        return [str(destination.relative_to(root)) for _, destination in copies]
    if not receipt_path.is_file() or not record_path.is_file():
        raise coverage.CoverageError("receipt and verification record must be retained together")
    receipt, record = _read(receipt_path), _read(record_path)
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    expected_receipt = {
        "schema_version": 1, "profile_id": profile_id,
        "profile_revision": profile["profile_revision"],
        "test_revision": attempt["source_revision"], "project": "Address Standardizer",
        "version": VERSION, "postgresql_version": pg, "architecture": architecture,
        "platform": platform, "endpoint": "current", "case_results": results,
        "archives": digests, "extension_archive": extension_name,
        "release_eligible": False, "redistribution_status": BLOCK,
    }
    if any(receipt.get(key) != value for key, value in expected_receipt.items()):
        raise coverage.CoverageError("receipt identity or archive hashes differ from attempt")
    ci, environment = receipt.get("ci"), receipt.get("environment")
    if (receipt.get("clean_system") is not True
            or receipt.get("dependency_check_profile") != "macho-system-dependencies-v1"
            or receipt.get("dependency_checks_passed") is not (results["macho-closure"] == "passed")
            or not isinstance(ci, dict) or ci.get("provider") != "github-actions"
            or str(ci.get("run_id")) != run_id
            or any(ci.get(key) != attempt["source_revision"]
                   for key in ("source_revision", "build_revision", "test_revision"))
            or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")
            or not isinstance(environment, dict) or environment.get("os") != "macos"
            or environment.get("architecture") != architecture
            or not re.fullmatch(r"\d+(?:\.\d+)*", str(environment.get("os_version", "")))
            or not environment.get("image_id")):
        raise coverage.CoverageError("receipt CI or runner identity is incomplete")
    reports = receipt.get("reports")
    if not isinstance(reports, dict):
        raise coverage.CoverageError("receipt report digests are missing")
    report_sources = {key: archive_dir / filename for key, filename in REPORTS.items()}
    present_reports = {key for key, source in report_sources.items() if source.is_file()}
    if set(reports) != present_reports:
        raise coverage.CoverageError("receipt report set differs from retained reports")
    for key, source in report_sources.items():
        if key in present_reports:
            if reports.get(key) != evidence.sha256_file(source):
                raise coverage.CoverageError(f"receipt digest differs for {key}")
        elif (key == "static_analysis" and results["macho-closure"] == "passed") or (key == "probe_output" and results["archive-suite"] == "passed"):
            raise coverage.CoverageError(f"passing receipt is missing {key}")
    if results["macho-closure"] == "passed":
        static = _read(report_sources["static_analysis"])
        actual = static.get("archives")
        if isinstance(actual, list):
            actual = {item["basename"]: item["sha256"] for item in actual}
        if actual != digests or static.get("passed") is not True or static.get("findings"):
            raise coverage.CoverageError("passing Mach-O report does not verify final archive bytes")

    expected_record = {
        "schema_version": 2, "scope": "publication", "profile_id": profile_id,
        "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
        "case_results": results, "test_revision": attempt["source_revision"], "ci": ci,
        "outcome": outcome, "sha256": digests[extension_name],
        "component": "address_standardizer", "project": "Address Standardizer",
        "version": VERSION, "platform": platform, "postgresql_version": pg,
        "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": pg},
        "prerequisite_archives": [], "release_eligible": False, "redistribution_status": BLOCK,
        "environment": environment,
    }
    if any(record.get(key) != value for key, value in expected_record.items()):
        raise coverage.CoverageError("verification record differs from receipt or archive bytes")
    coverage.validate_verification_record(record, support, root)
    evidence.retain(receipt_path, evidence_dir / receipt_path.name, copies)
    evidence.retain(record_path, evidence_dir / record_path.name, copies)
    if outcome == "passed":
        copies.append((record_path, record_destination))
    _copy(copies)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    try:
        for path in import_run(args.root, args.core_archives, args.archives, args.run_id, args.target):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Address Standardizer macOS import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
