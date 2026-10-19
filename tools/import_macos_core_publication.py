#!/usr/bin/env python3
"""Validate and retain one PostgreSQL macOS core publication run."""

import argparse
from pathlib import Path
import re
import sys

import coverage
import emit_macos_core_publication as publication
import macos_publication_evidence as evidence


MAX_EVIDENCE_BYTES = evidence.MAX_EVIDENCE_BYTES


def _copy(source, destination, copies):
    evidence.retain(source, destination, copies)


def _attempt(path, run_id, profile):
    raw = evidence.read_json_object(path)
    steps = raw.get("steps")
    if (str(raw.get("run_id")) != str(run_id)
            or raw.get("profile_id") != profile["profile_id"]
            or not coverage.REVISION.fullmatch(str(raw.get("source_revision", "")))
            or not isinstance(steps, dict) or set(steps) != set(profile["case_ids"])
            or any(value not in {"success", "failure", "skipped"} for value in steps.values())):
        raise coverage.CoverageError("raw attempt identity, revision, or outcomes do not match profile and run")
    results = {case: {"success": "passed", "failure": "failed", "skipped": "skipped"}[value]
               for case, value in steps.items()}
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    return raw, results, outcome


def import_run(root, archive_artifact, verification_artifact, run_id,
               postgresql_version, architecture):
    root, archive_artifact, verification_artifact = map(
        Path, (root, archive_artifact, verification_artifact))
    run_id, postgresql_version = str(run_id), str(postgresql_version)
    if (not re.fullmatch(r"\d+", run_id) or not re.fullmatch(r"\d+\.\d+", postgresql_version)
            or architecture not in {"x86_64", "arm64"}):
        raise coverage.CoverageError("expected a numeric run ID, selected PostgreSQL version, and macOS architecture")
    profile = publication._profile(root, postgresql_version, architecture)
    platform = f"macos-{architecture}"
    archive_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    archive = archive_artifact / archive_name
    attempt_path = verification_artifact / "publication-attempt.json"
    if not attempt_path.is_file():
        raise coverage.CoverageError("verification artifact has no raw publication attempt")
    attempt, results, outcome = _attempt(attempt_path, run_id, profile)
    record_path = verification_artifact / f"{archive_name[:-7]}-current-{run_id}.json"
    target = root / "support/evidence" / f"macos-core-publication-{run_id}" / f"postgresql-{postgresql_version}" / architecture
    if not record_path.is_file():
        if outcome == "passed":
            raise coverage.CoverageError("passing attempt is missing its publication record")
        copies = []
        _copy(attempt_path, target / attempt_path.name, copies)
        steps_path = verification_artifact / "publication-steps.json"
        if steps_path.is_file():
            _copy(steps_path, target / steps_path.name, copies)
        evidence.copy_retained(copies)
        return [str(destination.relative_to(root)) for _, destination in copies]

    if archive.is_symlink() or not archive.is_file():
        raise coverage.CoverageError(f"missing final PostgreSQL archive {archive_name}")
    digest = evidence.sha256_file(archive)
    evidence.check_sidecar(archive, digest, "missing checksum sidecar for {name}")
    record = evidence.read_json_object(record_path)
    support = coverage.load_json(root / "support.json")
    coverage.validate_verification_record(record, support, root, allow_stale=False)
    revision = attempt["source_revision"]
    ci = record.get("ci")
    expected = {"schema_version": 2, "scope": "publication", "profile_id": profile["profile_id"],
                "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
                "case_results": results, "outcome": outcome, "test_revision": revision,
                "component": "postgresql", "version": postgresql_version,
                "postgresql_version": postgresql_version, "platform": platform, "sha256": digest}
    if (any(record.get(key) != value for key, value in expected.items())
            or record.get("profile_revision") not in profile["compatible_profile_revisions"]
            or not isinstance(ci, dict) or ci.get("provider") != "github-actions"
            or str(ci.get("run_id")) != run_id
            or not str(ci.get("run_url", "")).startswith("https://github.com/")
            or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")
            or any(ci.get(key) != revision for key in ("source_revision", "build_revision", "test_revision"))):
        raise coverage.CoverageError("record identity, run revision, profile, outcomes, or archive digest is invalid")
    environment = record.get("environment", {})
    if (environment.get("os") != "macos" or environment.get("architecture") != architecture
            or environment.get("endpoint") != "current"
            or environment.get("dependency_check_profile") != publication.DEPENDENCY_PROFILE):
        raise coverage.CoverageError("publication record does not identify the fresh macOS verifier")
    if outcome == "passed" and (environment.get("clean_system") is not True
                                 or environment.get("dependency_checks_passed") is not True):
        raise coverage.CoverageError("passing publication requires a clean runner and dependency checks")
    if (attempt.get("archives") != {archive_name: digest}
            or attempt.get("archive_present") is not True):
        raise coverage.CoverageError("raw attempt archive identity differs from final archive bytes")

    static = verification_artifact / "static-analysis.json"
    symbols = verification_artifact / "debug-symbols" / "index.json"
    diagnostics = verification_artifact / "diagnostics.json"
    if outcome == "passed":
        if not all(path.is_file() for path in (static, symbols, diagnostics)):
            raise coverage.CoverageError("passing publication requires Mach-O, dSYM, and diagnostic reports")
        digests = {archive_name: digest}
        static_report = evidence.read_json_object(static)
        if (static_report.get("archives") != [{"basename": archive_name, "sha256": digest}]
                or static_report.get("passed") is not True):
            raise coverage.CoverageError("Mach-O static report does not pass for the final archive")
        symbol_report = evidence.read_json_object(symbols)
        entries = symbol_report.get("files")
        if (symbol_report.get("schema_version") != 1 or not isinstance(entries, list) or not entries
                or any(not isinstance(item, dict) or item.get("archive") != archive_name
                       or item.get("archive_sha256") != digest for item in entries)):
            raise coverage.CoverageError("dSYM index does not bind entries to the final archive")
        diagnostic_report = evidence.read_json_object(diagnostics)
        if (diagnostic_report.get("archives") != digests
                or diagnostic_report.get("platform") != "macos"
                or diagnostic_report.get("architecture") != architecture
                or diagnostic_report.get("postgresql_version") != postgresql_version
                or not isinstance(diagnostic_report.get("postgresql_failure"), dict)):
            raise coverage.CoverageError("diagnostic report does not match the core publication")

    copies = []
    for source, name in ((record_path, record_path.name), (attempt_path, attempt_path.name),
                         (verification_artifact / "publication-steps.json", "publication-steps.json"),
                         (static, "static-analysis.json"), (symbols, "debug-symbols-index.json"),
                         (diagnostics, "diagnostics.json")):
        if source.is_file():
            _copy(source, root / "support/verification" / name if source == record_path else target / name, copies)
    if (archive_artifact / (archive_name + ".sha256")).is_file():
        _copy(archive_artifact / (archive_name + ".sha256"), target / (archive_name + ".sha256"), copies)
    evidence.copy_retained(copies)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archive-artifact", type=Path, required=True)
    parser.add_argument("--verification-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.archive_artifact, args.verification_artifact,
                                   args.run_id, args.postgresql_version, args.architecture)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"macOS core publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
