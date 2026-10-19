#!/usr/bin/env python3
"""Validate and retain one PostgreSQL Windows publication target."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import coverage
import emit_windows_core_publication as publication
import emit_windows_publication_records as combined
import import_windows_publication as windows_import


MAX_EVIDENCE_BYTES = windows_import.MAX_EVIDENCE_BYTES


def _retain(root, copies):
    for source, destination in copies:
        if (source.is_symlink() or not source.is_file()
                or source.stat().st_size > MAX_EVIDENCE_BYTES):
            raise coverage.CoverageError(
                f"evidence must be a regular file at most {MAX_EVIDENCE_BYTES} bytes: {source}")
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return [str(destination.relative_to(root)) for _, destination in copies]


def _attempt(artifact, run_id, profile):
    attempt = windows_import._find(artifact, "publication-attempt.json", required=False)
    steps = windows_import._find(artifact, "publication-steps.json", required=False)
    if attempt is None:
        raise coverage.CoverageError("incomplete publication artifact has no raw attempt")
    for path in (attempt, steps):
        if path is not None and (path.is_symlink() or path.stat().st_size > MAX_EVIDENCE_BYTES):
            raise coverage.CoverageError("raw attempt evidence exceeds size limit or is not a regular file")
    raw = combined._json(attempt, "publication attempt")
    raw_steps = raw.get("steps")
    if (str(raw.get("run_id")) != str(run_id)
            or not isinstance(raw.get("source_revision"), str)
            or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", raw["source_revision"])
            or not isinstance(raw_steps, dict)
            or set(raw_steps) != {"archive-suite", "symbols", "diagnostics"}
            or set(raw_steps) != set(profile["case_ids"])
            or any(value not in {"success", "failure", "skipped"} for value in raw_steps.values())):
        raise coverage.CoverageError("publication attempt identity, revision, or steps are invalid")
    outcomes = {case: "passed" if value == "success" else "failed" if value == "failure" else "skipped"
                for case, value in raw_steps.items()}
    outcome = ("failed" if "failed" in outcomes.values() else
               "skipped" if "skipped" in outcomes.values() else "passed")
    if outcome == "passed":
        raise coverage.CoverageError("incomplete publication artifact cannot retain a passing raw attempt")
    if steps is not None and combined._json(steps, "publication steps") != outcomes:
        raise coverage.CoverageError("publication steps do not correspond to the raw attempt")
    return attempt, steps, raw, outcomes


def _verify_attempt(attempt, steps, record, run_id, profile):
    raw = combined._json(attempt, "publication attempt")
    raw_steps = raw.get("steps")
    if (str(raw.get("run_id")) != str(run_id)
            or raw.get("source_revision") != record.get("test_revision")
            or not isinstance(raw_steps, dict)
            or set(raw_steps) != {"archive-suite", "symbols", "diagnostics"}
            or set(raw_steps) != set(profile["case_ids"])
            or any(value not in {"success", "failure", "skipped"} for value in raw_steps.values())):
        raise coverage.CoverageError("publication attempt identity or steps do not match the record")
    outcomes = {case: "passed" if value == "success" else "failed" if value == "failure" else "skipped"
                for case, value in raw_steps.items()}
    if combined._json(steps, "publication steps") != outcomes:
        raise coverage.CoverageError("publication steps do not correspond to the raw attempt")
    if record.get("case_results") != outcomes:
        raise coverage.CoverageError("record outcomes differ from raw attempt")


def import_run(root, build_artifact, verification_artifact, run_id, postgresql_version):
    root, build_artifact, verification_artifact = map(Path, (root, build_artifact, verification_artifact))
    run_id, postgresql_version = str(run_id), str(postgresql_version)
    if not re.fullmatch(r"[0-9]+", run_id) or not re.fullmatch(r"\d+\.\d+", postgresql_version):
        raise coverage.CoverageError("run ID must be numeric and PostgreSQL version must be major.minor")
    profile = publication._target_profile(root, postgresql_version)
    archive_name = f"postgresql-{postgresql_version}-windows-x86_64.tar.gz"
    archive = windows_import._find(build_artifact, archive_name, required=False)
    core_archives = [path for path in build_artifact.rglob("postgresql-*-windows-x86_64.tar.gz")
                     if path.is_file() and not path.is_symlink()]
    if archive is not None and (len(core_archives) != 1 or core_archives[0] != archive):
        raise coverage.CoverageError("build artifact must contain exactly one selected PostgreSQL archive")
    record_name = f"{archive_name[:-7]}-current-{run_id}.json"
    record_path = windows_import._find(verification_artifact, record_name, required=False)
    attempt = windows_import._find(verification_artifact, "publication-attempt.json", required=False)
    steps = windows_import._find(verification_artifact, "publication-steps.json", required=False)
    if archive is None or record_path is None:
        if record_path is not None:
            raise coverage.CoverageError("publication record exists without its PostgreSQL archive")
        attempt, steps, raw, outcomes = _attempt(verification_artifact, run_id, profile)
        evidence = root / "support/evidence" / f"windows-publication-{run_id}" / f"postgresql-{postgresql_version}"
        copies = [(attempt, evidence / "publication-attempt.json")]
        if steps is not None:
            copies.append((steps, evidence / "publication-steps.json"))
        return _retain(root, copies)
    core_records = [path for path in verification_artifact.rglob("postgresql-*-windows-x86_64-current-" + run_id + ".json")
                    if path.is_file() and not path.is_symlink()]
    if len(core_records) != 1 or core_records[0] != record_path:
        raise coverage.CoverageError("verification artifact must contain exactly one PostgreSQL core record")

    sidecar = windows_import._find(build_artifact, archive_name + ".sha256", required=False)
    if sidecar is None:
        raise coverage.CoverageError("PostgreSQL archive is missing its checksum sidecar")
    digest = combined.sha256_file(archive)
    combined._sidecar(sidecar, archive_name, digest)
    record = combined._json(record_path, "PostgreSQL publication record")
    if record.get("component") != "postgresql" or record.get("project") is not None or record.get("assembled_core") is not None:
        raise coverage.CoverageError("record is not core-only PostgreSQL evidence")
    coverage.validate_verification_record(
        record, coverage.load_json(root / "support.json"), root, allow_stale=False)
    ci = record.get("ci")
    revision = record.get("test_revision")
    if (record.get("schema_version") != 2 or record.get("scope") != "publication"
            or record.get("profile_id") != profile["profile_id"]
            or record.get("profile_revision") != profile["profile_revision"]
            or record.get("test_cases") != profile["case_ids"]
            or record.get("version") != postgresql_version
            or record.get("postgresql_version") != postgresql_version
            or record.get("platform") != "windows-x86_64" or record.get("sha256") != digest
            or not isinstance(ci, dict) or ci.get("provider") != "github-actions"
            or ci.get("run_id") != run_id
            or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")
            or any(ci.get(key) != revision for key in ("source_revision", "build_revision", "test_revision"))
            or not isinstance(revision, str)
            or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", revision)):
        raise coverage.CoverageError("PostgreSQL publication record identity or archive digest is invalid")
    environment = record.get("environment", {})
    if (environment.get("os") != "windows" or environment.get("architecture") != "x86_64"
            or environment.get("endpoint") != "current"
            or environment.get("dependency_check_profile") != publication.DEPENDENCY_PROFILE):
        raise coverage.CoverageError("PostgreSQL publication environment is invalid")
    results = record.get("case_results")
    if not isinstance(results, dict) or set(results) != set(profile["case_ids"]):
        raise coverage.CoverageError("PostgreSQL publication record has invalid case outcomes")
    outcome = ("failed" if "failed" in results.values() else
               "skipped" if "skipped" in results.values() else "passed")
    if record.get("outcome") != outcome:
        raise coverage.CoverageError("PostgreSQL record outcome does not match case outcomes")
    _verify_attempt(attempt, steps, record, run_id, profile)

    static = windows_import._find(verification_artifact, "static-analysis.json", required=False)
    diagnostics = windows_import._find(verification_artifact, "diagnostics.json", required=False)
    symbols = windows_import._find(build_artifact, "index.json", required=False)
    if outcome == "passed":
        if static is None or diagnostics is None or symbols is None:
            raise coverage.CoverageError("passed record requires PE report, PDB index, and diagnostics")
        combined.validate_static_report(static, [archive])
        publication._symbol_report(symbols, archive)
        publication._diagnostic(diagnostics, archive, postgresql_version)
        if environment.get("clean_system") is not True or environment.get("dependency_checks_passed") is not True:
            raise coverage.CoverageError("passed PostgreSQL evidence requires clean system and dependency checks")
    copies = []
    evidence = root / "support/evidence" / f"windows-publication-{run_id}" / f"postgresql-{postgresql_version}"
    for source, filename in ((static, "static-analysis.json"), (symbols, "debug-symbols-index.json"),
                             (diagnostics, "diagnostics.json"), (attempt, "publication-attempt.json"),
                             (steps, "publication-steps.json")):
        if source is not None:
            copies.append((source, evidence / filename))
    copies.append((record_path, root / "support/verification" / record_name))
    return _retain(root, copies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--build-artifact", type=Path, required=True)
    parser.add_argument("--verification-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--postgresql-version", required=True)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.build_artifact, args.verification_artifact,
                                   args.run_id, args.postgresql_version)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Windows core publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
