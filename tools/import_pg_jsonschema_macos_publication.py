#!/usr/bin/env python3
"""Validate and retain one pg_jsonschema macOS arm64 publication attempt."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import coverage
import emit_pg_jsonschema_macos_publication as publication

MAX_FILE_BYTES = 8 * 1024 * 1024


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"invalid or missing evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"expected a JSON object in {path}")
    return value


def _digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _retain(source, destination, copies):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_FILE_BYTES:
        raise coverage.CoverageError(f"evidence must be a regular file no larger than {MAX_FILE_BYTES} bytes: {source}")
    if destination.exists() and (destination.is_symlink() or destination.read_bytes() != source.read_bytes()):
        raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    copies.append((source, destination))


def _copy(copies, root):
    root = Path(root).resolve()
    for source, destination in copies:
        if not destination.parent.resolve().is_relative_to(root):
            raise coverage.CoverageError(f"evidence path escapes repository root: {destination}")
        parent = destination.parent
        while parent != root and parent != parent.parent:
            if parent.is_symlink():
                raise coverage.CoverageError(f"evidence path crosses a symbolic link: {parent}")
            parent = parent.parent
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def import_run(root, core_archives, archives, run_id):
    root, core_archives, archives = map(Path, (root, core_archives, archives))
    root = root.resolve()
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run_id must be numeric")
    publication_dir = archives / "publication"
    attempt_path = publication_dir / "attempt.json"
    attempt = _read(attempt_path)
    profile = coverage.verification_profile(root, publication.PROFILE_ID)
    if (attempt.get("schema_version") != 1 or str(attempt.get("run_id")) != run_id
            or attempt.get("profile_id") != publication.PROFILE_ID
            or attempt.get("architecture") != publication.ARCHITECTURE
            or attempt.get("postgresql_version") != publication.PG_VERSION
            or attempt.get("pg_jsonschema_version") != publication.EXTENSION_VERSION
            or attempt.get("core_run_id") != publication.CORE_RUN_ID
            or attempt.get("release_eligible") is not False
            or attempt.get("core_status") != publication.CORE_STATUS
            or attempt.get("release_blockers") != publication.RELEASE_BLOCKERS
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))):
        raise coverage.CoverageError("attempt identity does not match requested run and profile")
    raw_steps = attempt.get("steps")
    allowed = {"success", "failure", "skipped", "cancelled", "timed_out"}
    if not isinstance(raw_steps, dict) or set(raw_steps) != publication.CASES or any(
            value not in allowed for value in raw_steps.values()):
        raise coverage.CoverageError("attempt must retain both publication case outcomes")
    results = {case: publication._step(raw_steps[case], case) for case in sorted(publication.CASES)}
    core_name = f"postgresql-{publication.PG_VERSION}-{publication.PLATFORM}.tar.gz"
    extension_name = f"pg_jsonschema-{publication.EXTENSION_VERSION}-postgresql-{publication.PG_VERSION}-{publication.PLATFORM}.tar.gz"
    core, extension = core_archives / core_name, archives / extension_name
    expected_presence = {core_name: core.is_file(), extension_name: extension.is_file()}
    if attempt.get("archives_present") != expected_presence:
        raise coverage.CoverageError("attempt archive presence differs from downloaded artifacts")
    evidence = root / "support/evidence" / f"pg-jsonschema-macos-publication-{run_id}" / publication.ARCHITECTURE
    copies = []
    _retain(attempt_path, evidence / "attempt.json", copies)
    for name, source in (("static-analysis.json", archives / "static-analysis.json"),
                         ("probe-output.txt", archives / "probe-output.txt"),
                         ("build-evidence.txt", archives / "build-evidence.txt"),
                         ("cargo-license-inventory.json", archives / "cargo-license-inventory.json")):
        if source.is_file():
            _retain(source, evidence / name, copies)
    receipt_path = publication_dir / "current-receipt.json"
    record_paths = sorted((publication_dir / "records").glob("*.json"))
    if not core.is_file() or not extension.is_file():
        if receipt_path.exists() or record_paths:
            raise coverage.CoverageError("receipt or record exists without both final archives")
        _copy(copies, root)
        return [str(destination.relative_to(root)) for _, destination in copies]
    digests = {core_name: _digest(core), extension_name: _digest(extension)}
    for archive in (core, extension):
        publication._sidecar(archive, digests[archive.name])
        _retain(Path(str(archive) + ".sha256"), evidence / (archive.name + ".sha256"), copies)
    if digests[core_name] != publication.CORE_SHA256:
        raise coverage.CoverageError("downloaded core differs from the pinned passed build")
    if attempt.get("archives") != digests:
        raise coverage.CoverageError("downloaded archive bytes differ from the raw attempt hashes")
    publication._metadata(extension)
    expected_reports = {key: _digest(path) for key, path in {
        "static_analysis": archives / "static-analysis.json",
        "probe_output": archives / "probe-output.txt",
        "build_evidence": archives / "build-evidence.txt",
        "cargo_license_inventory": archives / "cargo-license-inventory.json",
    }.items() if path.is_file()}
    if attempt.get("reports") != expected_reports:
        raise coverage.CoverageError("raw attempt report hashes differ from downloaded report bytes")
    if results["archive-suite"] == "passed" and ("probe_output" not in expected_reports or
            "pg_jsonschema|0.3.4" not in (archives / "probe-output.txt").read_text(encoding="utf-8")):
        raise coverage.CoverageError("passing archive suite lacks the expected SQL probe output")
    if results["static-analysis"] == "passed":
        publication._static_report(archives / "static-analysis.json", digests)
    if any(result != "passed" for result in results.values()):
        if receipt_path.exists() or record_paths:
            raise coverage.CoverageError("failed or incomplete attempt must not contain a receipt or record")
        _copy(copies, root)
        return [str(destination.relative_to(root)) for _, destination in copies]
    if not {"static_analysis", "build_evidence", "cargo_license_inventory"} <= set(expected_reports):
        raise coverage.CoverageError("passing candidate is missing required static analysis or build evidence")
    if len(record_paths) > 1:
        raise coverage.CoverageError("expected one verification record")
    if receipt_path.exists() != bool(record_paths):
        raise coverage.CoverageError("receipt and verification record must exist together")
    if receipt_path.exists():
        receipt, record = _read(receipt_path), _read(record_paths[0])
        ci = receipt.get("ci")
        if (receipt.get("schema_version") != 1 or receipt.get("profile_id") != publication.PROFILE_ID
                or receipt.get("profile_revision") != profile["profile_revision"]
                or receipt.get("test_revision") != attempt["source_revision"]
                or receipt.get("project") != "pg_jsonschema"
                or receipt.get("version") != publication.EXTENSION_VERSION
                or receipt.get("postgresql_version") != publication.PG_VERSION
                or receipt.get("architecture") != publication.ARCHITECTURE
                or receipt.get("platform") != publication.PLATFORM
                or receipt.get("endpoint") != "current"
                or receipt.get("case_results") != results or receipt.get("archives") != digests
                or receipt.get("extension_archive") != extension_name
                or receipt.get("reports") != expected_reports or receipt.get("release_eligible") is not False
                or receipt.get("core_status") != publication.CORE_STATUS
                or receipt.get("release_blockers") != publication.RELEASE_BLOCKERS
                or receipt.get("clean_system") is not True
                or receipt.get("dependency_check_profile") != "macho-system-dependencies-v1"
                or receipt.get("dependency_checks_passed") != (results["static-analysis"] == "passed")):
            raise coverage.CoverageError("receipt identity or evidence hashes are inconsistent")
        environment = receipt.get("environment")
        if (not isinstance(environment, dict) or environment.get("os") != "macos"
                or environment.get("architecture") != publication.ARCHITECTURE
                or environment.get("clean_system") is not True
                or environment.get("endpoint") != "current"
                or environment.get("dependency_checks_passed") != (results["static-analysis"] == "passed")):
            raise coverage.CoverageError("receipt environment differs from the tested platform and outcomes")
        if (not isinstance(ci, dict) or ci.get("provider") != "github-actions"
                or str(ci.get("run_id")) != run_id
                or any(ci.get(key) != attempt["source_revision"] for key in
                       ("source_revision", "build_revision", "test_revision"))
                or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")):
            raise coverage.CoverageError("receipt CI provenance differs from raw attempt")
        coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
        expected_outcome = ("failed" if "failed" in results.values() else
                            "skipped" if "skipped" in results.values() else "passed")
        if (record.get("profile_revision") != profile["profile_revision"]
                or record.get("profile_id") != publication.PROFILE_ID
                or record.get("test_cases") != profile["case_ids"]
                or record.get("case_results") != results or record.get("outcome") != expected_outcome
                or record.get("ci") != ci or record.get("sha256") != digests[extension_name]
                or record.get("component") != "pg_jsonschema"
                or record.get("project") != "pg_jsonschema"
                or record.get("version") != publication.EXTENSION_VERSION
                or record.get("platform") != publication.PLATFORM
                or record.get("postgresql_version") != publication.PG_VERSION
                or record.get("test_revision") != attempt["source_revision"]
                or record.get("assembled_core") != {"archive": core_name, "sha256": digests[core_name],
                                                     "version": publication.PG_VERSION}
                or record.get("release_eligible") is not False
                or record.get("core_status") != publication.CORE_STATUS
                or record.get("release_blockers") != publication.RELEASE_BLOCKERS):
            raise coverage.CoverageError("verification record differs from receipt or archive bytes")
        if record.get("environment") != environment:
            raise coverage.CoverageError("verification record environment differs from receipt")
        _retain(receipt_path, evidence / receipt_path.name, copies)
        _retain(record_paths[0], evidence / record_paths[0].name, copies)
        _retain(record_paths[0], root / "support/verification" / record_paths[0].name, copies)
    _copy(copies, root)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_archives, args.archives, args.run_id)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_jsonschema macOS publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
