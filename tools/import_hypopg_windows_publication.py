#!/usr/bin/env python3
"""Validate and retain one hypopg Windows publication attempt."""

import argparse
import json
from pathlib import Path
import shutil
import sys

import coverage
import emit_hypopg_windows_publication as publication

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
    if destination.is_symlink() or (destination.exists() and destination.read_bytes() != source.read_bytes()):
        raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    copies.append((source, destination))


def _copy(copies, root):
    root = Path(root).resolve()
    for source, destination in copies:
        if not destination.parent.resolve().is_relative_to(root):
            raise coverage.CoverageError(f"retained evidence path escapes repository root: {destination}")
        parent = destination.parent
        while parent != root and parent != parent.parent:
            if parent.is_symlink():
                raise coverage.CoverageError(f"retained evidence path crosses a symbolic link: {parent}")
            parent = parent.parent
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def import_run(root, core_artifact, extension_artifact, run_id):
    root, core_artifact, extension_artifact = map(Path, (root, core_artifact, extension_artifact))
    root = root.resolve()
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run_id must be numeric")
    support = coverage.load_json(root / "support.json")
    profile = coverage.verification_profile(root, publication.PROFILE_ID)
    if (profile["scope"] != "publication" or profile["platforms"] != [publication.PLATFORM]
            or profile["case_ids"] != sorted(publication.CASES)):
        raise coverage.CoverageError("registered profile does not match the scoped hypopg target")
    pub = extension_artifact / "publication"
    attempt_path = pub / "attempt.json"
    attempt = _read(attempt_path)
    if (attempt.get("schema_version") != 1 or str(attempt.get("run_id")) != run_id
            or attempt.get("profile_id") != publication.PROFILE_ID
            or attempt.get("architecture") != publication.ARCHITECTURE
            or attempt.get("postgresql_version") != publication.PG_VERSION
            or attempt.get("hypopg_version") != publication.HYPOPG_VERSION
            or attempt.get("release_eligible") is not False
            or attempt.get("core_status") != publication.CORE_STATUS
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))):
        raise coverage.CoverageError("raw attempt identity does not match the requested run and profile")
    raw_steps = attempt.get("steps")
    if (not isinstance(raw_steps, dict) or set(raw_steps) != publication.CASES
            or any(value not in {"success", "failure", "skipped", "cancelled", "timed_out"}
                   for value in raw_steps.values())):
        raise coverage.CoverageError("raw attempt must retain each publication case outcome")
    results = {case: publication._step(value, case) for case, value in raw_steps.items()}
    evidence = root / "support/evidence" / f"hypopg-windows-publication-{run_id}" / publication.ARCHITECTURE
    copies = []
    _retain(attempt_path, evidence / "attempt.json", copies)
    core_name = f"postgresql-{publication.PG_VERSION}-{publication.PLATFORM}.tar.gz"
    extension_name = f"hypopg-{publication.HYPOPG_VERSION}-postgresql-{publication.PG_VERSION}-{publication.PLATFORM}.tar.gz"
    core_archive, extension_archive = core_artifact / core_name, extension_artifact / extension_name
    receipt_path = pub / "current-receipt.json"
    record_paths = sorted((pub / "records").glob("*.json"))
    if not core_archive.is_file() or not extension_archive.is_file():
        if receipt_path.exists() or record_paths:
            raise coverage.CoverageError("archive-bound receipt or record exists without both archives")
        for name in ("static-analysis.json", "probe-output.txt", "prerequisite-output.txt"):
            source = extension_artifact / name
            if source.is_file():
                _retain(source, evidence / name, copies)
        _copy(copies, root)
        return [str(dest.relative_to(root)) for _, dest in copies]

    digests = {core_name: publication.sha256_file(core_archive),
               extension_name: publication.sha256_file(extension_archive)}
    for archive in (core_archive, extension_archive):
        publication._sidecar(archive, digests[archive.name])
    if digests[core_name] != publication.CORE_SHA256:
        raise coverage.CoverageError("core archive does not match the pinned PostgreSQL 18.6 artifact")
    publication._metadata(extension_archive)
    if attempt.get("archives") != digests:
        raise coverage.CoverageError("raw attempt archive hashes differ from final archive bytes")
    if not receipt_path.is_file():
        raise coverage.CoverageError("complete archives require a publication receipt")
    receipt = _read(receipt_path)
    ci = receipt.get("ci")
    expected_receipt = {
        "schema_version": 1, "profile_id": publication.PROFILE_ID,
        "profile_revision": profile["profile_revision"], "test_revision": attempt["source_revision"],
        "project": "HypoPG", "version": publication.HYPOPG_VERSION,
        "postgresql_version": publication.PG_VERSION, "architecture": publication.ARCHITECTURE,
        "platform": publication.PLATFORM, "endpoint": "current", "case_results": results,
        "archives": digests, "extension_archive": extension_name,
        "release_eligible": False, "core_status": publication.CORE_STATUS,
    }
    if any(receipt.get(key) != value for key, value in expected_receipt.items()):
        raise coverage.CoverageError("receipt identity or archive hashes differ from the raw attempt")
    if (not isinstance(ci, dict) or ci.get("provider") != "github-actions" or str(ci.get("run_id")) != run_id
            or any(ci.get(key) != attempt["source_revision"]
                   for key in ("source_revision", "build_revision", "test_revision"))
            or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")):
        raise coverage.CoverageError("receipt CI provenance differs from the raw attempt")
    if (receipt.get("clean_system") is not True
            or receipt.get("dependency_check_profile") != "windows-pe-archive-relocation-v1"
            or not isinstance(receipt.get("reports"), dict)
            or not isinstance(receipt.get("environment"), dict)
            or receipt["environment"].get("os") != "windows"
            or receipt["environment"].get("architecture") != publication.ARCHITECTURE
            or not receipt["environment"].get("os_version") or not receipt["environment"].get("image_id")):
        raise coverage.CoverageError("receipt environment or static-check profile is incomplete")
    report_sources = {"static_analysis": extension_artifact / "static-analysis.json",
                      "probe_output": extension_artifact / "probe-output.txt",
                      "pe_dependency_analysis": extension_artifact / "pe-dependency-analysis.json"}
    expected_reports = {}
    for key, source in report_sources.items():
        if source.is_file():
            expected_reports[key] = publication.sha256_file(source)
    if receipt["reports"] != expected_reports:
        raise coverage.CoverageError("receipt report hashes differ from the retained reports")
    static_path = extension_artifact / "static-analysis.json"
    if results["static-analysis"] == "passed":
        static = _read(static_path)
        if (static.get("passed") is not True or static.get("archives") != digests
                or static.get("native_extension_files") != ["hypopg/lib/hypopg.dll"]
                or not static.get("inspected_files")
                or static.get("pe_dependency_analysis_sha256") !=
                publication.sha256_file(extension_artifact / "pe-dependency-analysis.json")):
            raise coverage.CoverageError("static-analysis report does not cover the final archives")
    if results["archive-suite"] == "passed":
        probe = extension_artifact / "probe-output.txt"
        if not probe.is_file() or "Index Scan using" not in probe.read_text(encoding="utf-8"):
            raise coverage.CoverageError("archive suite output does not show the hypothetical index plan")
    if results["static-analysis"] == "passed":
        pe = _read(extension_artifact / "pe-dependency-analysis.json")
        if (pe.get("outcome") != "passed" or
                {item.get("basename"): item.get("sha256") for item in pe.get("archives", [])
                 if isinstance(item, dict)} != digests or
                "lib/hypopg.dll" not in pe.get("inspected_files", [])):
            raise coverage.CoverageError("PE dependency analysis does not cover the final archives")
    if len(record_paths) != 1:
        raise coverage.CoverageError("expected exactly one hypopg publication record")
    record_path = record_paths[0]
    record = _read(record_path)
    coverage.validate_verification_record(record, support, root)
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    expected_record = {
        "profile_id": publication.PROFILE_ID, "component": "hypopg", "project": "HypoPG",
        "version": publication.HYPOPG_VERSION, "postgresql_version": publication.PG_VERSION,
        "platform": publication.PLATFORM, "case_results": results, "outcome": outcome,
        "test_cases": profile["case_ids"], "ci": ci, "test_revision": attempt["source_revision"],
        "sha256": digests[extension_name],
        "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": publication.PG_VERSION},
        "prerequisite_archives": [], "release_eligible": False,
        "core_status": publication.CORE_STATUS,
    }
    if (any(record.get(key) != value for key, value in expected_record.items())
            or record_path.name != f"hypopg-{publication.HYPOPG_VERSION}-postgresql-{publication.PG_VERSION}-{publication.PLATFORM}-current-{run_id}.json"
            or record.get("environment", {}).get("clean_system") is not True
            or record.get("environment", {}).get("endpoint") != "current"
            or any(record.get("environment", {}).get(key) != receipt["environment"].get(key)
                   for key in ("os", "os_version", "architecture", "image_id"))
            or record.get("environment", {}).get("dependency_check_profile") != receipt["dependency_check_profile"]
            or record.get("environment", {}).get("dependency_checks_passed") != receipt.get("dependency_checks_passed")):
        raise coverage.CoverageError("record identity, archive or environment differs from receipt")
    for source in (receipt_path, static_path, extension_artifact / "probe-output.txt",
                   extension_artifact / "pe-dependency-analysis.json", record_path):
        if source.is_file():
            destination = (evidence / "verification-record.json"
                           if source == record_path else evidence / source.name)
            _retain(source, destination, copies)
    _retain(record_path, root / "support/verification" / record_path.name, copies)
    _copy(copies, root)
    return [str(dest.relative_to(root)) for _, dest in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True)
    parser.add_argument("--extension-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact, args.extension_artifact, args.run_id)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"hypopg Windows publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
