#!/usr/bin/env python3
"""Emit archive-bound PostgreSQL macOS core publication evidence."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

import coverage
import macos_publication_evidence as evidence


CASES = {"archive-suite", "diagnostics", "symbols"}
DEPENDENCY_PROFILE = "macho-system-dependencies-v1"


def _profile(root, version, architecture):
    support = coverage.load_json(Path(root) / "support.json")
    releases = coverage.load_json(Path(root) / "support/postgresql-releases.json")
    if version not in coverage.release_snapshot(releases, support):
        raise coverage.CoverageError(f"PostgreSQL {version} is not selected")
    profile_id = f"postgresql-publication-macos-{architecture}-{version}"
    try:
        profile = coverage.verification_profile(root, profile_id)
    except coverage.CoverageError as exc:
        raise coverage.CoverageError(f"registered target profile {profile_id!r} is required") from exc
    if (profile["scope"] != "publication" or profile["platforms"] != [f"macos-{architecture}"]
            or profile["case_ids"] != sorted(CASES) or not profile["sources_available"]):
        raise coverage.CoverageError("registered profile does not match the macOS core publication target")
    return profile


def _json(path, label):
    return evidence.read_json_object(path)


def _check_static_archives(report, archive_name, digest):
    if report.get("archives") != [{"basename": archive_name, "sha256": digest}]:
        raise coverage.CoverageError("Mach-O static report archive hash does not match final archive bytes")


def emit(root, archives, output, postgresql_version, architecture, revision,
         os_version, image_id, step_results, static_report, symbol_report,
         diagnostic_report, environ=None):
    root, archives, output = map(Path, (root, archives, output))
    environ = os.environ if environ is None else environ
    if architecture not in {"x86_64", "arm64"} or not re.fullmatch(r"\d+\.\d+", postgresql_version):
        raise coverage.CoverageError("expected a selected PostgreSQL major.minor and macOS architecture")
    if not coverage.REVISION.fullmatch(str(revision)):
        raise coverage.CoverageError("test revision must be a full Git commit hash")
    if not re.fullmatch(r"\d+(?:\.\d+)*", str(os_version)) or not image_id:
        raise coverage.CoverageError("macOS runner version and image identifier are required")
    run_id, repository, server_url = (environ.get(key, "") for key in
                                      ("GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL"))
    if not run_id.isdigit() or not repository or not server_url:
        raise coverage.CoverageError("GitHub Actions run provenance is required")
    profile = _profile(root, postgresql_version, architecture)
    raw_steps = _json(step_results, "step results")
    if (set(raw_steps) != set(CASES) or set(raw_steps) != set(profile["case_ids"])
            or any(value not in {"success", "failure", "skipped"} for value in raw_steps.values())):
        raise coverage.CoverageError("step results must match all registered profile cases")
    results = {case: {"success": "passed", "failure": "failed", "skipped": "skipped"}[raw_steps[case]]
               for case in profile["case_ids"]}
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    platform = f"macos-{architecture}"
    archive_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    archive = archives / archive_name
    output.mkdir(parents=True, exist_ok=True)
    attempt_path = output / "publication-attempt.json"
    attempt = {"schema_version": 1, "run_id": run_id, "source_revision": revision,
               "profile_id": profile["profile_id"], "postgresql_version": postgresql_version,
               "architecture": architecture, "steps": raw_steps,
               "archive_present": archive.is_file()}
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "publication-steps.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if outcome != "passed" or not archive.is_file():
        return [attempt_path]
    digest = evidence.sha256_file(archive)
    evidence.check_sidecar(archive, digest, "missing checksum sidecar for {name}")
    digests = {archive_name: digest}
    static = _json(static_report, "Mach-O static analysis")
    if static.get("passed") is not True or not static.get("inspected_files"):
        raise coverage.CoverageError("passing core publication requires a successful Mach-O static analysis report")
    _check_static_archives(static, archive_name, digest)
    symbols = _json(symbol_report, "dSYM index")
    entries = symbols.get("files")
    if (symbols.get("schema_version") != 1 or not isinstance(entries, list) or not entries
            or any(not isinstance(item, dict) or item.get("archive") != archive_name
                   or item.get("archive_sha256") != digest for item in entries)):
        raise coverage.CoverageError("dSYM index must bind every entry to the final PostgreSQL archive")
    diagnostics = _json(diagnostic_report, "diagnostic")
    if diagnostics.get("archives") != digests:
        raise coverage.CoverageError("diagnostic report archive hash does not match final archive bytes")
    if (diagnostics.get("platform") != "macos" or diagnostics.get("architecture") != architecture
            or diagnostics.get("postgresql_version") != postgresql_version
            or not isinstance(diagnostics.get("postgresql_failure"), dict)):
        raise coverage.CoverageError("core diagnostic report identity or PostgreSQL failure evidence is invalid")
    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    record = {"schema_version": 2, "scope": "publication", "profile_id": profile["profile_id"],
              "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
              "case_results": results, "test_revision": revision, "ci": ci, "outcome": outcome,
              "sha256": digest, "component": "postgresql", "version": postgresql_version,
              "platform": platform, "postgresql_version": postgresql_version,
              "environment": {"os": "macos", "os_version": str(os_version),
                              "architecture": architecture, "clean_system": True,
                              "endpoint": "current", "image_id": str(image_id),
                              "dependency_check_profile": DEPENDENCY_PROFILE,
                              "dependency_checks_passed": True}}
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root,
                                          allow_stale=False)
    record_path = output / f"{archive_name[:-7]}-current-{run_id}.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    attempt["archives"] = digests
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [attempt_path, record_path]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--step-results", type=Path, required=True)
    parser.add_argument("--static-report", type=Path, required=True)
    parser.add_argument("--symbol-report", type=Path, required=True)
    parser.add_argument("--diagnostic-report", type=Path, required=True)
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.archives, args.output, args.postgresql_version,
                         args.architecture, args.revision, args.os_version, args.image_id,
                         args.step_results, args.static_report, args.symbol_report,
                         args.diagnostic_report):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"macOS core publication: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
