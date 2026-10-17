#!/usr/bin/env python3
"""Emit checksum-bound macOS publication records from verification step results."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import coverage

DEPENDENCY_PROFILE = "macho-system-dependencies-v1"
STEP_CASES = {"archive-suite": "archive-suite", "symbols": "symbols", "diagnostics": "diagnostics"}


def _fail(message):
    raise coverage.CoverageError(message)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_report(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"{label} report is required and must be valid")
    if not isinstance(value, dict):
        _fail(f"{label} report must be an object")
    return value


def _validate_report_archives(report, architecture, archives, label, require_static=False, require_passed=True):
    if require_passed and report.get("passed") is not True:
        _fail(f"{label} report did not pass")
    if report.get("architecture") != architecture:
        _fail(f"{label} report architecture does not match runner")
    if require_static and (not isinstance(report.get("inspected_files"), list)
                           or not report["inspected_files"]):
        _fail("static analysis report inspected_files must be nonempty")
    expected = sorted((archive.name, sha256_file(archive)) for archive in archives)
    actual = report.get("archives")
    if not isinstance(actual, dict):
        if isinstance(actual, list):
            try:
                actual = {item["basename"]: item["sha256"] for item in actual}
            except (KeyError, TypeError):
                _fail(f"{label} report archives are malformed")
        else:
            _fail(f"{label} report archives are missing")
    try:
        pairs = sorted((name, digest.lower()) for name, digest in actual.items())
    except (AttributeError, TypeError):
        _fail(f"{label} report archives are malformed")
    if pairs != expected:
        _fail(f"{label} report archives do not match final archives")


def _sidecar(path, name, digest):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fail(f"missing checksum for {name}")
    if (len(lines) != 1 or not re.fullmatch(rf"[0-9a-fA-F]{{64}}\s+\*?{re.escape(name)}", lines[0])
            or lines[0].split()[0].lower() != digest):
        _fail(f"checksum sidecar does not match {name}")


def _step_result(value, step):
    if value in {"success", "passed"}:
        return "passed"
    if value in {"failure", "failed", "timed_out"}:
        return "failed"
    if value in {"skipped", "cancelled"}:
        return "skipped"
    _fail(f"{step} step result must be success, failure, or skipped")


def emit(root, archives, output, postgresql_version, revision, os_version, architecture,
         image_id, step_results, static_report, diagnostic_report):
    root, archives, output = Path(root), Path(archives), Path(output)
    if architecture not in {"x86_64", "arm64"}:
        _fail("macOS runner architecture must be x86_64 or arm64")
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", revision or ""):
        _fail("test revision must be a full Git commit hash")
    if not isinstance(os_version, str) or not re.fullmatch(r"\d+(?:\.\d+)*", os_version):
        _fail("macOS version must be numeric dotted version")
    if not isinstance(image_id, str) or not image_id:
        _fail("runner image identifier is required")
    if not isinstance(step_results, dict) or set(step_results) != set(STEP_CASES):
        _fail("step_results must identify archive-suite, symbols, and diagnostics")
    results = {case: _step_result(step_results[step], step) for step, case in STEP_CASES.items()}
    outcome = ("failed" if "failed" in results.values()
               else "skipped" if "skipped" in results.values() else "passed")
    profile_id = f"macos-publication-current-{architecture}"
    platform = f"macos-{architecture}"
    profile = coverage.verification_profile(root, profile_id)
    if profile["scope"] != "publication" or platform not in profile["platforms"]:
        _fail("registered profile is not a macOS publication profile for this architecture")
    if (not profile["sources_available"]
            or profile["case_ids"] != sorted(STEP_CASES.values())):
        _fail("registered macOS publication profile must contain exactly the archive-suite, symbols, and diagnostics cases")
    if not re.fullmatch(r"\d+\.\d+", postgresql_version or ""):
        _fail("PostgreSQL version must be major.minor")
    vector_version = "0.8.7"
    names = (f"postgresql-{postgresql_version}-{platform}.tar.gz",
             f"pgvector-{vector_version}-postgresql-{postgresql_version}-{platform}.tar.gz")
    digests = {}
    for name in names:
        archive = archives / name
        if not archive.is_file():
            _fail(f"missing final archive {name}")
        digest = sha256_file(archive)
        _sidecar(archives / f"{name}.sha256", name, digest)
        digests[name] = digest
    if outcome == "passed":
        static = _read_report(static_report, "static analysis")
        diagnostic = _read_report(diagnostic_report, "diagnostic")
        paths = [archives / name for name in names]
        _validate_report_archives(static, architecture, paths, "static analysis", True)
        _validate_report_archives(diagnostic, architecture, paths, "diagnostic", require_passed=False)
        if (diagnostic.get("platform") != "macos"
                or diagnostic.get("postgresql_version") != postgresql_version
                or diagnostic.get("pgvector_version") != vector_version
                or not isinstance(diagnostic.get("system_failure"), dict)
                or not isinstance(diagnostic.get("postgresql_failure"), dict)
                or not isinstance(diagnostic["system_failure"].get("exit_code"), int)
                or diagnostic["system_failure"]["exit_code"] == 0
                or not diagnostic["system_failure"].get("loader_output")
                or not isinstance(diagnostic["postgresql_failure"].get("exit_code"), int)
                or diagnostic["postgresql_failure"]["exit_code"] == 0
                or not diagnostic["postgresql_failure"].get("server_log")):
            _fail("diagnostic report does not identify both required failure investigations")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "")
    if not run_id.isdigit() or not repository or not server_url:
        _fail("GitHub Actions run provenance is required")
    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server_url}/{repository}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    support = coverage.load_json(root / "support.json")
    records = []
    for name, component, version in ((names[0], "postgresql", postgresql_version),
                                     (names[1], "vector", vector_version)):
        record = {
            "schema_version": 2, "scope": "publication", "profile_id": profile_id,
            "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
            "case_results": results, "test_revision": revision, "ci": ci, "outcome": outcome,
            "sha256": digests[name], "component": component, "version": version,
            "platform": platform, "postgresql_version": postgresql_version,
            "environment": {"os": "macos", "os_version": os_version,
                            "architecture": architecture, "clean_system": True,
                            "endpoint": "current", "image_id": image_id,
                            "dependency_check_profile": DEPENDENCY_PROFILE,
                            "dependency_checks_passed": results["archive-suite"] == "passed"},
        }
        if component == "vector":
            record["project"] = "pgvector"
            record["assembled_core"] = {"archive": names[0], "sha256": digests[names[0]],
                                         "version": postgresql_version}
        coverage.validate_verification_record(record, support, root)
        records.append(record)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for record, name in zip(records, names):
        path = output / f"{name[:-7]}-current-{run_id}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--archive-suite-result", required=True)
    parser.add_argument("--symbols-result", required=True)
    parser.add_argument("--diagnostics-result", required=True)
    parser.add_argument("--static-report", type=Path)
    parser.add_argument("--diagnostic-report", type=Path)
    args = parser.parse_args()
    try:
        steps = {"archive-suite": args.archive_suite_result, "symbols": args.symbols_result,
                 "diagnostics": args.diagnostics_result}
        paths = emit(args.root, args.archives, args.output, args.postgresql_version,
                     os.environ.get("GITHUB_SHA", ""), args.os_version,
                     args.architecture, args.image_id, steps, args.static_report,
                     args.diagnostic_report)
        for path in paths:
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"macOS publication record: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
