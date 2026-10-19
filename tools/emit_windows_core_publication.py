#!/usr/bin/env python3
"""Emit one archive-bound PostgreSQL Windows publication record or a raw attempt."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

import coverage
import emit_windows_publication_records as combined
import windows_core_target_config


DEPENDENCY_PROFILE = combined.DEPENDENCY_PROFILE


def _target_profile(root, postgresql_version):
    """Resolve the selected release and its registered target-specific profile."""
    support = coverage.load_json(Path(root) / "support.json")
    snapshot = coverage.load_json(Path(root) / "support/postgresql-releases.json")
    if postgresql_version not in coverage.release_snapshot(snapshot, support):
        raise coverage.CoverageError(f"PostgreSQL {postgresql_version} is not a selected release")
    profile_id = f"postgresql-publication-windows-x86_64-{postgresql_version}"
    try:
        selected = coverage.verification_profile(root, profile_id)
    except coverage.CoverageError as exc:
        raise coverage.CoverageError(f"registered target profile {profile_id!r} is required") from exc
    if (selected["scope"] != "publication" or selected["platforms"] != ["windows-x86_64"]
            or selected["case_ids"] != ["archive-suite", "diagnostics", "symbols"]
            or not selected["sources_available"]):
        raise coverage.CoverageError("selected PostgreSQL Windows profile is incompatible with core publication")
    return selected


def _diagnostic(path, archive, pg_version):
    report = combined._json(path, "diagnostic report")
    expected = {archive.name: combined.sha256_file(archive)}
    if report.get("archives") != expected:
        raise coverage.CoverageError("diagnostic report archive does not match the PostgreSQL archive")
    if (report.get("schema_version") != 1 or report.get("platform") != "windows"
            or report.get("architecture") != "x86_64"
            or report.get("postgresql_version") != pg_version
            or "pgvector_version" in report):
        raise coverage.CoverageError("core diagnostic report identity is invalid")
    system = report.get("system_failure")
    server = report.get("postgresql_failure")
    if (not isinstance(system, dict) or system.get("kind") != "missing-bundled-runtime-dll"
            or not isinstance(system.get("exit_code"), int) or system["exit_code"] == 0
            or not system.get("missing_library")
            or (not system.get("failure_text") and system.get("ntstatus") != "0xC0000135")):
        raise coverage.CoverageError("diagnostic report system_failure evidence is missing")
    if (not isinstance(server, dict) or server.get("kind") != "server-error"
            or not isinstance(server.get("exit_code"), int) or server["exit_code"] == 0
            or not server.get("failure_text") or not server.get("server_log")):
        raise coverage.CoverageError("diagnostic report postgresql_failure evidence is missing")


def _symbol_report(path, archive):
    report = combined._json(path, "PDB index")
    entries = report.get("files")
    digest = combined.sha256_file(archive)
    if not isinstance(entries, list) or not entries or any(not isinstance(entry, dict) for entry in entries):
        raise coverage.CoverageError("PDB index files must be a nonempty array of objects")
    matching = [entry for entry in entries if isinstance(entry, dict)
                and entry.get("archive") == archive.name]
    if not matching or any(entry.get("archive_sha256") != digest for entry in matching):
        raise coverage.CoverageError("PDB index does not bind symbols to the PostgreSQL archive")
    if set(entry.get("archive") for entry in entries if isinstance(entry, dict)) != {archive.name}:
        raise coverage.CoverageError("PDB index must cover only the PostgreSQL archive")
    index_root = Path(path).parent
    for entry in matching:
        pdb_path = entry.get("pdb_path")
        if (not isinstance(pdb_path, str) or Path(pdb_path).is_absolute()
                or ".." in Path(pdb_path).parts or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("pdb_sha256", "")))):
            raise coverage.CoverageError("PDB index has an invalid PDB path or checksum")
        pdb = index_root / pdb_path
        if not pdb.is_file() or combined.sha256_file(pdb) != entry["pdb_sha256"]:
            raise coverage.CoverageError("PDB index PDB file is missing or has a different checksum")


def _write_attempt(output, run_id, revision, results):
    outcomes = {case: ("success" if result == "passed" else "failure" if result == "failed" else "skipped")
                for case, result in results.items()}
    raw = {"schema_version": 1, "run_id": run_id, "source_revision": revision, "steps": outcomes}
    steps = results
    output.mkdir(parents=True, exist_ok=True)
    (output / "publication-attempt.json").write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "publication-steps.json").write_text(
        json.dumps(steps, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit(root, archives, output, postgresql_version, revision, os_version, image_id,
         step_results, static_report=None, symbol_report=None, diagnostic_report=None):
    root, archives, output = map(Path, (root, archives, output))
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", revision):
        raise coverage.CoverageError("test revision must be a full Git commit hash")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version):
        raise coverage.CoverageError("Windows version must be numeric dotted version")
    if not isinstance(image_id, str) or not image_id:
        raise coverage.CoverageError("runner image identifier is required")
    profile = _target_profile(root, postgresql_version)
    results = combined._json(step_results, "step results")
    if set(results) != {"archive-suite", "symbols", "diagnostics"} or set(results) != set(profile["case_ids"]):
        raise coverage.CoverageError("step results must identify exactly archive-suite, symbols, and diagnostics")
    if any(result not in {"passed", "failed", "skipped"} for result in results.values()):
        raise coverage.CoverageError("step results must be passed, failed, or skipped")
    outcome = ("failed" if "failed" in results.values() else
               "skipped" if "skipped" in results.values() else "passed")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "")
    if not run_id.isdigit() or not repository or not server_url:
        raise coverage.CoverageError("GitHub Actions run provenance is required")
    _write_attempt(output, run_id, revision, results)
    archive_name = f"postgresql-{postgresql_version}-windows-x86_64.tar.gz"
    archive = archives / archive_name
    if results["archive-suite"] != "passed":
        return []
    if not archive.is_file():
        raise coverage.CoverageError(f"missing PostgreSQL archive {archive_name}")
    core_archives = [path for path in archives.rglob("postgresql-*-windows-x86_64.tar.gz")
                     if path.is_file() and not path.is_symlink()]
    if len(core_archives) != 1 or core_archives[0] != archive:
        raise coverage.CoverageError("expected exactly one PostgreSQL Windows archive")
    digest = combined.sha256_file(archive)
    combined._sidecar(archives / (archive_name + ".sha256"), archive_name, digest)
    manifest = windows_core_target_config._manifest(archive)
    build_revision = manifest.get("source_revision") if isinstance(manifest, dict) else None
    if not isinstance(build_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", build_revision):
        raise coverage.CoverageError("PostgreSQL archive has no valid build source revision")
    if any(manifest.get(key) != value for key, value in {
        "component": "postgresql", "version": postgresql_version,
        "postgresql_version": postgresql_version, "platform": "windows",
        "architecture": "x86_64",
    }.items()):
        raise coverage.CoverageError("PostgreSQL archive manifest does not match the selected Windows target")
    build_match = re.fullmatch(r"github-([1-9][0-9]*)-([1-9][0-9]*)", str(manifest.get("build_id", "")))
    if build_match is None:
        raise coverage.CoverageError("PostgreSQL archive has no valid producer run identity")
    if outcome == "passed":
        if static_report is None or symbol_report is None or diagnostic_report is None:
            raise coverage.CoverageError("passed core publication requires PE, PDB, and diagnostic reports")
        combined.validate_static_report(static_report, [archive])
        _symbol_report(symbol_report, archive)
        _diagnostic(diagnostic_report, archive, postgresql_version)
    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server_url}/{repository}/actions/runs/{run_id}",
          "source_revision": build_revision, "build_revision": build_revision, "test_revision": revision,
          "build_run_id": build_match.group(1), "build_run_attempt": build_match.group(2)}
    record = {"schema_version": 2, "scope": "publication", "profile_id": profile["profile_id"],
              "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
              "case_results": results, "test_revision": revision, "ci": ci, "outcome": outcome,
              "sha256": digest, "component": "postgresql", "version": postgresql_version,
              "platform": "windows-x86_64", "postgresql_version": postgresql_version,
              "environment": {"os": "windows", "os_version": os_version, "architecture": "x86_64",
                              "clean_system": True, "endpoint": "current", "image_id": image_id,
                              "dependency_check_profile": DEPENDENCY_PROFILE,
                              "dependency_checks_passed": outcome == "passed"}}
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root,
                                          allow_stale=False)
    destination = output / f"{archive_name[:-7]}-current-{run_id}.json"
    output.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [destination]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--step-results", type=Path, required=True)
    parser.add_argument("--static-report", type=Path)
    parser.add_argument("--symbol-report", type=Path)
    parser.add_argument("--diagnostic-report", type=Path)
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.archives, args.output, args.postgresql_version,
                         args.revision, args.os_version, args.image_id, args.step_results,
                         args.static_report, args.symbol_report, args.diagnostic_report):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Windows core publication record: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
