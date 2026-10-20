#!/usr/bin/env python3
"""Emit Windows publication records bound to downloaded archives and reports."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile

import coverage


PROFILE_ID = "windows-publication-current-x86_64"
DEPENDENCY_PROFILE = "windows-pe-runtime-v1"
MAX_ARCHIVE_METADATA_BYTES = 1024 * 1024


def _fail(message):
    raise coverage.CoverageError(message)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path, description):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"{description} is required and must be valid JSON")
    if not isinstance(value, dict):
        _fail(f"{description} must be a JSON object")
    return value


def _sidecar(path, name, digest):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fail(f"missing checksum for {name}: {exc}")
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^\s]+)", lines[0]) if len(lines) == 1 else None
    if not match or Path(match.group(2)).name != name or match.group(1).lower() != digest:
        _fail(f"checksum sidecar does not match {name}")


def _archive_provenance(path, member_name, label):
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = [member for member in archive.getmembers() if member.name == member_name]
            if len(members) != 1 or not members[0].isfile() or members[0].size > MAX_ARCHIVE_METADATA_BYTES:
                _fail(f"{label} archive requires one bounded {member_name}")
            stream = archive.extractfile(members[0])
            if stream is None:
                _fail(f"{label} archive metadata cannot be read")
            value = json.loads(stream.read(MAX_ARCHIVE_METADATA_BYTES + 1).decode("utf-8"))
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read {label} archive provenance: {exc}")
    if not isinstance(value, dict):
        _fail(f"{label} archive provenance must be a JSON object")
    source_revision = value.get("source_revision")
    build_id = value.get("build_id")
    match = re.fullmatch(r"github-([1-9][0-9]*)-([1-9][0-9]*)", str(build_id or ""))
    if (not isinstance(source_revision, str)
            or not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", source_revision)
            or match is None):
        _fail(f"{label} archive has invalid source revision or build ID")
    return source_revision, build_id, match.group(1), match.group(2)


def _archive_report(path, archives, description):
    report = _json(path, description)
    actual = report.get("archives")
    if not isinstance(actual, list):
        _fail(f"{description} archives are missing")
    try:
        actual_pairs = sorted((item["basename"], item["sha256"].lower()) for item in actual)
    except (KeyError, AttributeError, TypeError):
        _fail(f"{description} archives are malformed")
    expected = sorted((p.name, sha256_file(p)) for p in archives)
    if actual_pairs != expected:
        _fail(f"{description} archives do not match downloaded archives")
    return report


def validate_static_report(path, archives):
    report = _archive_report(path, archives, "PE static report")
    if report.get("outcome") != "passed":
        _fail("PE static report did not pass")
    if report.get("platform") != "windows" or report.get("architecture") != "x86_64":
        _fail("PE static report platform or architecture does not match Windows x86_64")
    if not isinstance(report.get("inspected_files"), list) or not report["inspected_files"]:
        _fail("PE static report inspected_files must be nonempty")


def validate_symbol_report(path, archives):
    report = _json(path, "symbol report")
    entries = report.get("files")
    if not isinstance(entries, list) or not entries:
        _fail("symbol report files must be nonempty")
    expected = {archive.name: sha256_file(archive) for archive in archives}
    represented = {entry.get("archive") for entry in entries if isinstance(entry, dict)}
    if represented != {p.name for p in archives}:
        _fail("symbol report must cover both downloaded archives")
    if any(not isinstance(entry, dict) or entry.get("archive_sha256") != expected.get(entry.get("archive"))
           for entry in entries):
        _fail("symbol report archive checksums do not match downloaded archives")


def validate_diagnostic_report(path, archives, pg_version, vector_version):
    report = _json(path, "diagnostic report")
    actual = report.get("archives")
    expected = {archive.name: sha256_file(archive) for archive in archives}
    if actual != expected:
        _fail("diagnostic report archives do not match downloaded archives")
    if report.get("schema_version") != 1 or report.get("platform") != "windows" or report.get("architecture") != "x86_64":
        _fail("diagnostic report identity is invalid")
    if report.get("postgresql_version") != pg_version or report.get("pgvector_version") != vector_version:
        _fail("diagnostic report component versions do not match archives")
    system = report.get("system_failure")
    server = report.get("postgresql_failure")
    if (not isinstance(system, dict) or system.get("kind") != "missing-bundled-runtime-dll"
            or not isinstance(system.get("exit_code"), int) or system["exit_code"] == 0
            or not system.get("missing_library")
            or (not system.get("failure_text") and system.get("ntstatus") != "0xC0000135")):
        _fail("diagnostic report system_failure evidence is missing")
    if (not isinstance(server, dict) or server.get("kind") != "server-error"
            or not isinstance(server.get("exit_code"), int) or server["exit_code"] == 0
            or not server.get("failure_text") or not server.get("server_log")):
        _fail("diagnostic report postgresql_failure evidence is missing")


def _selected_vector_version(root, pg_version):
    support = coverage.load_json(Path(root) / "support.json")
    snapshot = coverage.load_json(Path(root) / "support" / "postgresql-releases.json")
    releases = coverage.release_snapshot(snapshot, support)
    _, targets = coverage.expected_targets(support, releases)
    versions = [version for project, version, pg, platform in targets
                if project == "vector" and pg == pg_version and platform == "windows-x86_64"]
    if not versions:
        _fail(f"no selected pgvector target for PostgreSQL {pg_version} windows-x86_64")
    return max(versions, key=lambda value: coverage.version_parts(value, "pgvector version"))


def emit(root, archives, output, pg_version, revision, os_version, image_id,
         step_results, static_report, symbol_report, diagnostic_report,
         dependency_checks_passed=True):
    root, archives, output = Path(root), Path(archives), Path(output)
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", revision):
        _fail("test revision must be a full Git commit hash")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version):
        _fail("Windows version must be numeric dotted version")
    if not isinstance(image_id, str) or not image_id:
        _fail("runner image identifier is required")
    if not isinstance(dependency_checks_passed, bool):
        _fail("dependency check result must be boolean")
    profile = coverage.verification_profile(root, PROFILE_ID)
    if profile["scope"] != "publication" or "windows-x86_64" not in profile["platforms"]:
        _fail("registered profile is not the Windows x86_64 publication profile")
    if not profile["sources_available"]:
        _fail("Windows publication profile sources are unavailable")
    results = _json(step_results, "step results")
    if set(results) != set(profile["case_ids"]):
        _fail("step results must identify exactly every registered profile case")
    if any(result not in {"passed", "failed", "skipped"} for result in results.values()):
        _fail("step results must be passed, failed, or skipped")
    outcome = ("failed" if "failed" in results.values() else
               "skipped" if "skipped" in results.values() else "passed")
    vector_version = _selected_vector_version(root, pg_version)
    names = (
        (f"postgresql-{pg_version}-windows-x86_64.tar.gz", "postgresql", pg_version),
        (f"pgvector-{vector_version}-postgresql-{pg_version}-windows-x86_64.tar.gz", "vector", vector_version),
    )
    digests = {}
    paths = {}
    for name, _, _ in names:
        path = archives / name
        digest = sha256_file(path)
        _sidecar(archives / f"{name}.sha256", name, digest)
        digests[name] = digest
        paths[name] = path
    build_provenance = {
        names[0][0]: _archive_provenance(paths[names[0][0]], "postgresql/manifest.json", "PostgreSQL"),
        names[1][0]: _archive_provenance(paths[names[1][0]], "metadata.json", "pgvector"),
    }
    if outcome == "passed":
        validate_static_report(static_report, list(paths.values()))
        validate_symbol_report(symbol_report, list(paths.values()))
        validate_diagnostic_report(diagnostic_report, list(paths.values()), pg_version, vector_version)
        if dependency_checks_passed is not True:
            _fail("passed records require successful dependency checks")

    support = coverage.load_json(root / "support.json")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    server_url = os.environ.get("GITHUB_SERVER_URL", "")
    if not run_id.isdigit() or not repository or not server_url:
        _fail("GitHub Actions run provenance is required")
    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server_url}/{repository}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    records = []
    for name, component, version in names:
        build_revision, build_id, build_run_id, build_run_attempt = build_provenance[name]
        record = {
            "schema_version": 2, "scope": "publication", "profile_id": PROFILE_ID,
            "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
            "case_results": results, "test_revision": revision, "ci": ci, "outcome": outcome,
            "sha256": digests[name], "component": component, "version": version,
            "platform": "windows-x86_64", "postgresql_version": pg_version,
            "environment": {"os": "windows", "os_version": os_version,
                            "architecture": "x86_64", "clean_system": True,
                            "endpoint": "current", "image_id": image_id,
                            "dependency_check_profile": DEPENDENCY_PROFILE,
                            "dependency_checks_passed": dependency_checks_passed},
        }
        record["ci"] = {**ci, "source_revision": build_revision, "build_revision": build_revision,
                        "build_run_id": build_run_id, "build_run_attempt": build_run_attempt}
        if component == "vector":
            record["project"] = "pgvector"
            record["assembled_core"] = {"archive": names[0][0], "sha256": digests[names[0][0]], "version": pg_version}
        coverage.validate_verification_record(record, support, root)
        records.append((name, record))
    output.mkdir(parents=True, exist_ok=True)
    result_paths = []
    for name, record in records:
        destination = output / f"{name[:-7]}-current-{run_id}.json"
        destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result_paths.append(destination)
    return result_paths


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
    parser.add_argument("--dependency-checks-passed", choices=("true", "false"), default="true")
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.archives, args.output, args.postgresql_version,
                         args.revision, args.os_version, args.image_id, args.step_results,
                         args.static_report, args.symbol_report, args.diagnostic_report,
                         args.dependency_checks_passed == "true"):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Windows publication record: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
