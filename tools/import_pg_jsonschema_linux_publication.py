#!/usr/bin/env python3
"""Validate and retain one Linux pg_jsonschema publication attempt."""

import argparse
import json
from pathlib import Path
import shutil
import sys

import coverage
import emit_pg_jsonschema_linux_publication as publication

MAX_FILE_BYTES = 8 * 1024 * 1024


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"invalid or missing JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"expected a JSON object in {path}")
    return value


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
            raise coverage.CoverageError(f"retained evidence path escapes repository root: {destination}")
        ancestor = destination.parent
        while ancestor != root and ancestor != ancestor.parent:
            if ancestor.is_symlink():
                raise coverage.CoverageError(f"retained evidence path crosses a symbolic link: {ancestor}")
            ancestor = ancestor.parent
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def _step_results(attempt):
    raw = attempt.get("steps")
    if not isinstance(raw, dict) or set(raw) != set(publication.CASES):
        raise coverage.CoverageError("attempt must retain both publication case outcomes")
    permitted = {"success", "failure", "skipped", "cancelled", "timed_out"}
    if any(value not in permitted for value in raw.values()):
        raise coverage.CoverageError("attempt contains an invalid publication case outcome")
    results = {case: publication._step(raw[case]) for case in publication.CASES}
    workflow = attempt.get("workflow_steps")
    if not isinstance(workflow, dict):
        raise coverage.CoverageError("raw attempt must retain build and verify workflow outcomes")
    expected = publication._case_results(workflow.get("verify"),
                                         "passed" if results["elf-closure"] == "passed" else
                                         "failed" if results["elf-closure"] == "failed" else None)
    if results != {"archive-suite": publication._step(expected[0]),
                   "elf-closure": publication._step(expected[1])}:
        raise coverage.CoverageError("case outcomes do not match retained workflow step outcomes")
    return results


def _retain_available(attempt_path, attempt, archives, evidence, copies):
    _retain(attempt_path, evidence / "attempt.json", copies)
    names = {
        "elf_closure": (archives / "static-analysis" / "pg_jsonschema.json", "elf-closure.json"),
        "probe_output": (archives / "probe-output.txt", "probe-output.txt"),
        "build_evidence": (archives / "build-evidence.txt", "build-evidence.txt"),
        "cargo_license_inventory": (archives / "cargo-license-inventory.json", "cargo-license-inventory.json"),
    }
    report_hashes = attempt.get("reports", {})
    for key, (source, name) in names.items():
        if source.is_file():
            if key in report_hashes and publication.digest(source) != report_hashes[key]:
                raise coverage.CoverageError(f"retained {key} report hash differs from raw attempt")
            _retain(source, evidence / name, copies)


def import_run(root, core_archives, archives, run_id):
    root, core_archives, archives = map(Path, (root, core_archives, archives))
    root = root.resolve()
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run_id must be numeric")
    attempt_path = archives / "publication" / "attempt.json"
    attempt = _read(attempt_path)
    architecture = attempt.get("architecture")
    if architecture not in publication.PROFILE_IDS:
        raise coverage.CoverageError("attempt architecture is unsupported")
    profile = coverage.verification_profile(root, publication.PROFILE_IDS[architecture])
    if (attempt.get("schema_version") != 1 or str(attempt.get("run_id")) != run_id
            or attempt.get("profile_id") != publication.PROFILE_IDS[architecture]
            or attempt.get("core_run_id") != publication.CORE_RUN_ID
            or attempt.get("postgresql_version") != publication.PG_VERSION
            or attempt.get("pg_jsonschema_version") != publication.EXTENSION_VERSION
            or attempt.get("release_eligible") is not False
            or attempt.get("redistribution_status") != "seahash-4.1.0-notice-unresolved"
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))):
        raise coverage.CoverageError("raw attempt identity does not match this run and profile")
    results = _step_results(attempt)
    workflow_steps = attempt.get("workflow_steps")
    if (not isinstance(workflow_steps, dict) or set(workflow_steps) != {"build", "verify"}
            or any(value not in {"success", "failure", "skipped", "cancelled", "timed_out"}
                   for value in workflow_steps.values())):
        raise coverage.CoverageError("raw attempt must retain build and verify workflow outcomes")
    platform = f"linux-{architecture}"
    archive_name = f"pg_jsonschema-{publication.EXTENSION_VERSION}-postgresql-{publication.PG_VERSION}-{platform}.tar.gz"
    core_name = f"postgresql-{publication.PG_VERSION}-{platform}.tar.gz"
    extension_archive, core_archive = archives / archive_name, core_archives / core_name
    for path in (extension_archive, core_archive):
        if path.is_symlink():
            raise coverage.CoverageError(f"archive must not be a symbolic link: {path}")
    present = attempt.get("archives_present")
    if (not isinstance(present, dict) or present != {core_name: core_archive.is_file(),
                                                    archive_name: extension_archive.is_file()}):
        raise coverage.CoverageError("raw attempt archive presence differs from downloaded files")
    evidence = root / "support/evidence" / f"pg_jsonschema-linux-publication-{run_id}" / architecture
    copies = []
    _retain_available(attempt_path, attempt, archives, evidence, copies)
    if not extension_archive.is_file() or not core_archive.is_file():
        if (archives / "publication" / "current-receipt.json").exists() or (archives / "publication" / "verification-record.json").exists():
            raise coverage.CoverageError("receipt or record exists without both final archives")
        _copy(copies, root)
        return [str(destination.relative_to(root)) for _, destination in copies]

    digests = {archive_name: publication.digest(extension_archive), core_name: publication.digest(core_archive)}
    publication._sidecar(extension_archive, digests[archive_name])
    publication._sidecar(core_archive, digests[core_name])
    if digests[core_name] != publication.CORE_SHA256[architecture]:
        raise coverage.CoverageError("downloaded core archive differs from the pinned current-profile archive")
    if attempt.get("archives") != digests:
        raise coverage.CoverageError("downloaded archive bytes differ from raw attempt hashes")
    _retain(Path(str(extension_archive) + ".sha256"), evidence / f"{archive_name}.sha256", copies)
    _retain(Path(str(core_archive) + ".sha256"), evidence / f"{core_name}.sha256", copies)
    static_path = archives / "static-analysis" / "pg_jsonschema.json"
    if static_path.is_file():
        static = _read(static_path)
        expected_static_archives = [{"basename": archive_name, "sha256": digests[archive_name]}]
        if (static.get("outcome") not in {"passed", "failed"}
                or static.get("architecture") != architecture
                or static.get("archives") != expected_static_archives
                or (static.get("outcome") == "passed") != (results["elf-closure"] == "passed")):
            raise coverage.CoverageError("ELF report outcome or checksum does not match the raw attempt")
    receipt_path = archives / "publication" / "current-receipt.json"
    record_path = archives / "publication" / "verification-record.json"
    if receipt_path.exists() != record_path.exists():
        raise coverage.CoverageError("receipt and verification record must be retained together")
    if not receipt_path.exists():
        _copy(copies, root)
        return [str(destination.relative_to(root)) for _, destination in copies]

    build_evidence = archives / "build-evidence.txt"
    build_text = build_evidence.read_text(encoding="utf-8")
    if (f"pg_jsonschema_source_commit={publication.SOURCE_COMMIT}" not in build_text
            or f"cargo_lock_sha256={publication.CARGO_LOCK_SHA256}" not in build_text):
        raise coverage.CoverageError("build evidence does not identify the exact upstream source and Cargo.lock")
    probe_output = archives / "probe-output.txt"
    if results["archive-suite"] == "passed" and (
            not probe_output.is_file()
            or f"PASS: pg_jsonschema {publication.EXTENSION_VERSION} on relocated PostgreSQL {publication.PG_VERSION} in Alpine 3.22"
            not in probe_output.read_text(encoding="utf-8")):
        raise coverage.CoverageError("passed archive suite lacks retained relocated Alpine probe output")

    receipt = _read(receipt_path)
    record = _read(record_path)
    expected_reports = {key: publication.digest(path) for key, path in {
        "elf_closure": archives / "static-analysis" / "pg_jsonschema.json",
        "build_evidence": archives / "build-evidence.txt",
        "cargo_license_inventory": archives / "cargo-license-inventory.json",
        "probe_output": archives / "probe-output.txt",
    }.items() if path.is_file()}
    if not {"elf_closure", "build_evidence", "cargo_license_inventory"} <= set(expected_reports):
        raise coverage.CoverageError("complete candidate evidence is missing a required report")
    if attempt.get("reports") != expected_reports:
        raise coverage.CoverageError("raw attempt report hashes differ from retained report bytes")
    ci = receipt.get("ci")
    if (receipt.get("schema_version") != 1 or receipt.get("profile_id") != publication.PROFILE_IDS[architecture]
            or receipt.get("profile_revision") != profile["profile_revision"]
            or receipt.get("test_revision") != attempt["source_revision"]
            or receipt.get("project") != "pg_jsonschema" or receipt.get("version") != publication.EXTENSION_VERSION
            or receipt.get("postgresql_version") != publication.PG_VERSION
            or receipt.get("architecture") != architecture or receipt.get("platform") != platform
            or receipt.get("endpoint") != "current" or receipt.get("case_results") != results
            or receipt.get("archives") != digests or receipt.get("extension_archive") != archive_name
            or receipt.get("reports") != expected_reports or receipt.get("release_eligible") is not False
            or receipt.get("redistribution_status") != "seahash-4.1.0-notice-unresolved"
            or receipt.get("clean_system") is not True
            or receipt.get("dependency_check_profile") != "linux-elf-alpine-relocation-v1"
            or receipt.get("dependency_checks_passed") != (results["elf-closure"] == "passed")):
        raise coverage.CoverageError("receipt identity, archive hashes or report hashes differ from evidence")
    if (not isinstance(ci, dict) or ci.get("provider") != "github-actions" or str(ci.get("run_id")) != run_id
            or any(ci.get(key) != attempt["source_revision"] for key in ("source_revision", "build_revision", "test_revision"))
            or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")):
        raise coverage.CoverageError("receipt CI provenance differs from raw attempt")
    expected_outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    if (record.get("profile_revision") != profile["profile_revision"]
            or record.get("test_cases") != profile["case_ids"] or record.get("case_results") != results
            or record.get("outcome") != expected_outcome or record.get("ci") != ci
            or record.get("test_revision") != attempt["source_revision"]
            or record.get("sha256") != digests[archive_name]
            or record.get("assembled_core") != {"archive": core_name, "sha256": digests[core_name], "version": publication.PG_VERSION}
            or record.get("release_eligible") is not False
            or record.get("redistribution_status") != "seahash-4.1.0-notice-unresolved"):
        raise coverage.CoverageError("verification record identity or checksums differ from receipt")
    if record.get("environment") != receipt.get("environment"):
        raise coverage.CoverageError("verification record environment differs from receipt")
    output_names = ((receipt_path, "current-receipt.json"),
                    (record_path, "verification-record.json"))
    for source, name in output_names:
        _retain(source, evidence / name, copies)
    _retain(record_path, root / "support/verification" /
            f"pg_jsonschema-{publication.EXTENSION_VERSION}-postgresql-{publication.PG_VERSION}-{platform}-current-{run_id}.json", copies)
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
        print(f"pg_jsonschema Linux publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
