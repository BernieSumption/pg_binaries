#!/usr/bin/env python3
"""Validate and retain archive-bound Windows publication evidence."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import coverage
import emit_windows_publication_records as publication


PROFILE_ID = publication.PROFILE_ID
MAX_EVIDENCE_BYTES = 1024 * 1024


def _find(directory, name, required=True):
    matches = [path for path in Path(directory).rglob(name) if path.is_file() and not path.is_symlink()]
    if len(matches) > 1:
        raise coverage.CoverageError(f"expected one {name} in artifact, found {len(matches)}")
    if not matches:
        if required:
            raise coverage.CoverageError(f"artifact is missing {name}")
        return None
    return matches[0]


def _read_json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"{label} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"{label} must be a JSON object")
    return value


def _retain_unbound_attempt(root, attempt, steps, run_id, profile):
    if attempt is None:
        raise coverage.CoverageError("archive-bound evidence is incomplete and publication attempt is missing")
    for path in (attempt, steps):
        if path is not None and (path.is_symlink() or path.stat().st_size > MAX_EVIDENCE_BYTES):
            raise coverage.CoverageError(f"raw attempt evidence exceeds {MAX_EVIDENCE_BYTES} bytes or is not a regular file")
    raw = _read_json(attempt, "publication attempt")
    revision = raw.get("source_revision")
    results = raw.get("steps")
    if (str(raw.get("run_id")) != str(run_id)
            or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision)
            or not isinstance(results, dict) or set(results) != set(profile["case_ids"])
            or any(value not in {"success", "failure", "skipped"} for value in results.values())):
        raise coverage.CoverageError("publication attempt identity, revision, or cases are invalid")
    outcomes = {case: "passed" if value == "success" else "failed" if value == "failure" else "skipped"
                for case, value in results.items()}
    outcome = "failed" if "failed" in outcomes.values() else "skipped" if "skipped" in outcomes.values() else "passed"
    if outcome == "passed":
        raise coverage.CoverageError("incomplete archive evidence cannot retain a passing attempt as failed or skipped evidence")
    if steps is not None and _read_json(steps, "publication steps") != outcomes:
        raise coverage.CoverageError("publication steps do not correspond to raw attempt")
    evidence = Path(root) / "support/evidence" / f"windows-publication-{run_id}"
    copies = [(attempt, evidence / "publication-attempt.json")]
    if steps is not None:
        copies.append((steps, evidence / "publication-steps.json"))
    for source, destination in copies:
        if not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise coverage.CoverageError(f"raw attempt evidence must be a regular file at most {MAX_EVIDENCE_BYTES} bytes: {source}")
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return [str(destination.relative_to(root)) for _, destination in copies]


def _verify_attempt(attempt, steps, records, run_id, revision):
    raw = _read_json(attempt, "publication attempt")
    actual_steps = raw.get("steps")
    if (str(raw.get("run_id")) != str(run_id) or raw.get("source_revision") != revision
            or not isinstance(actual_steps, dict)
            or set(actual_steps) != {"archive-suite", "symbols", "diagnostics"}
            or any(value not in {"success", "failure", "skipped"} for value in actual_steps.values())):
        raise coverage.CoverageError("publication attempt identity or steps do not match records")
    outcomes = _read_json(steps, "publication steps")
    expected = {"archive-suite": "passed" if actual_steps["archive-suite"] == "success" else
                "failed" if actual_steps["archive-suite"] == "failure" else "skipped",
                "symbols": "passed" if actual_steps["symbols"] == "success" else
                "failed" if actual_steps["symbols"] == "failure" else "skipped",
                "diagnostics": "passed" if actual_steps["diagnostics"] == "success" else
                "failed" if actual_steps["diagnostics"] == "failure" else "skipped"}
    if outcomes != expected:
        raise coverage.CoverageError("publication steps do not correspond to raw attempt")
    expected_results = {"archive-suite": outcomes["archive-suite"],
                        "symbols": outcomes["symbols"], "diagnostics": outcomes["diagnostics"]}
    if any(record.get("case_results") != expected_results for record in records):
        raise coverage.CoverageError("record case outcomes differ from publication steps")


def import_run(root, build_artifact, verification_artifact, run_id, postgresql_version="18.6"):
    root, build_artifact, verification_artifact = map(Path, (root, build_artifact, verification_artifact))
    run_id = str(run_id)
    if not re.fullmatch(r"\d+", run_id) or not re.fullmatch(r"\d+(?:\.\d+)*", postgresql_version):
        raise coverage.CoverageError("run ID and PostgreSQL version must be numeric")
    profile = coverage.verification_profile(root, PROFILE_ID)
    if (profile["scope"] != "publication" or "windows-x86_64" not in profile["platforms"]
            or not profile["sources_available"]):
        raise coverage.CoverageError("registered profile is not the current Windows publication profile")
    vector_version = publication._selected_vector_version(root, postgresql_version)
    names = [f"postgresql-{postgresql_version}-windows-x86_64.tar.gz",
             f"pgvector-{vector_version}-postgresql-{postgresql_version}-windows-x86_64.tar.gz"]
    archives = [_find(build_artifact, name, required=False) for name in names]
    static = _find(verification_artifact, "static-analysis.json", required=False)
    diagnostics = _find(verification_artifact, "diagnostics.json", required=False)
    symbols = _find(build_artifact, "index.json", required=False)
    attempt = _find(verification_artifact, "publication-attempt.json", required=False)
    steps = _find(verification_artifact, "publication-steps.json", required=False)
    candidates = sorted(verification_artifact.rglob("*-current-" + run_id + ".json"))
    if any(archive is None for archive in archives) or len(candidates) != 2:
        return _retain_unbound_attempt(root, attempt, steps, run_id, profile)
    digests = {path.name: publication.sha256_file(path) for path in archives}
    for archive in archives:
        sidecar = _find(build_artifact, archive.name + ".sha256", required=False)
        if sidecar is None:
            return _retain_unbound_attempt(root, attempt, steps, run_id, profile)
        publication._sidecar(sidecar, archive.name, digests[archive.name])

    if static is None or diagnostics is None or symbols is None or attempt is None or steps is None:
        raise coverage.CoverageError("archive-bound records exist but required reports or attempt files are missing")
    records = [_read_json(path, "publication record") for path in candidates]
    if len(records) != 2:
        raise coverage.CoverageError("expected PostgreSQL and pgvector publication records for this run")

    publication.validate_static_report(static, archives)
    publication.validate_symbol_report(symbols, archives)
    publication.validate_diagnostic_report(diagnostics, archives, postgresql_version, vector_version)
    ci = records[0].get("ci")
    revision = records[0].get("test_revision")
    expected_names = {
        "postgresql": names[0], "vector": names[1],
    }
    if {path.name for path in candidates} != {
            f"{archive_name[:-7]}-current-{run_id}.json" for archive_name in expected_names.values()}:
        raise coverage.CoverageError("publication record filenames do not match component archives and run")
    support = coverage.load_json(root / "support.json")
    if not isinstance(ci, dict) or ci.get("run_id") != run_id or ci.get("provider") != "github-actions":
        raise coverage.CoverageError("records do not identify the requested GitHub Actions run")
    if (not str(ci.get("run_url", "")).startswith("https://github.com/")
            or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")
            or ci.get("test_revision") != revision):
        raise coverage.CoverageError("record CI test revision or run URL is inconsistent")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise coverage.CoverageError("record test revision is invalid")
    by_component = {record.get("component"): record for record in records}
    if set(by_component) != set(expected_names):
        raise coverage.CoverageError("records must cover PostgreSQL and pgvector")
    archive_by_component = {"postgresql": archives[0], "vector": archives[1]}
    for component, archive_name in expected_names.items():
        record = by_component[component]
        archive_member = "postgresql/manifest.json" if component == "postgresql" else "metadata.json"
        label = "PostgreSQL" if component == "postgresql" else "pgvector"
        build_revision, _, build_run_id, build_run_attempt = publication._archive_provenance(
            archive_by_component[component], archive_member, label)
        record_ci = record.get("ci")
        expected_ci = {**ci, "source_revision": build_revision, "build_revision": build_revision,
                       "build_run_id": build_run_id, "build_run_attempt": build_run_attempt}
        if (record_ci != expected_ci or record.get("test_revision") != revision):
            raise coverage.CoverageError(f"{component} record CI provenance does not match its archive")
        coverage.validate_verification_record(record, support, root)
        if (record.get("profile_id") != PROFILE_ID or record.get("profile_revision") not in profile["compatible_profile_revisions"]
                or record.get("platform") != "windows-x86_64" or record.get("postgresql_version") != postgresql_version
                or record.get("sha256") != digests[archive_name]
                or record.get("version") != (postgresql_version if component == "postgresql" else vector_version)
                or record.get("test_cases") != profile["case_ids"]
                or record.get("scope") != "publication"
                or record.get("environment", {}).get("endpoint") != "current"
                or record.get("environment", {}).get("clean_system") is not True
                or record.get("environment", {}).get("dependency_check_profile") != "windows-pe-runtime-v1"):
            raise coverage.CoverageError(f"{component} record identity or archive digest is invalid")
        if component == "vector" and record.get("project") != "pgvector":
            raise coverage.CoverageError("pgvector record project identity is invalid")
        if component == "vector" and record.get("assembled_core") != {
                "archive": names[0], "sha256": digests[names[0]], "version": postgresql_version}:
            raise coverage.CoverageError("pgvector record does not identify the downloaded PostgreSQL core archive")
    if by_component["postgresql"].get("case_results") != by_component["vector"].get("case_results"):
        raise coverage.CoverageError("publication records disagree on case outcomes")
    _verify_attempt(attempt, steps, records, run_id, revision)

    evidence = root / "support/evidence" / f"windows-publication-{run_id}"
    copies = [(static, evidence / "static-analysis.json"), (symbols, evidence / "debug-symbols-index.json"),
              (diagnostics, evidence / "diagnostics.json"), (attempt, evidence / "publication-attempt.json"),
              (steps, evidence / "publication-steps.json")]
    verification = root / "support/verification"
    for source in candidates:
        copies.append((source, verification / source.name))
    for source, destination in copies:
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise coverage.CoverageError(f"evidence must be a regular file at most {MAX_EVIDENCE_BYTES} bytes: {source}")
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--build-artifact", type=Path, required=True)
    parser.add_argument("--verification-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--postgresql-version", default="18.6")
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.build_artifact, args.verification_artifact,
                                   args.run_id, args.postgresql_version)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Windows publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
