#!/usr/bin/env python3
"""Emit archive-bound verification evidence for a selected macOS TIGER build."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile

import coverage

VERSION = "2025.2"
POSTGIS_VERSION = "3.6.4"
CASES = ["archive-suite", "static-analysis"]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def archive_metadata(path):
    try:
        with tarfile.open(path, "r:gz") as archive:
            member = archive.getmember("metadata.json")
            if not member.isfile() or member.size > 1024 * 1024:
                raise coverage.CoverageError(f"invalid metadata.json in {path.name}")
            value = json.load(archive.extractfile(member))
    except (OSError, tarfile.TarError, KeyError, ValueError) as exc:
        raise coverage.CoverageError(f"cannot read metadata from {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"metadata in {path.name} must be an object")
    return value


def emit(root, core_dir, postgis_dir, tiger_dir, output, pg, architecture,
         archive_suite, static_analysis, os_version, image_id, environ=None):
    root, core_dir, postgis_dir, tiger_dir, output = map(
        Path, (root, core_dir, postgis_dir, tiger_dir, output))
    platform = f"macos-{architecture}"
    profile_id = f"tiger-publication-macos-{architecture}-{pg}"
    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or profile["platforms"] != [platform]
            or profile["case_ids"] != CASES or not profile["sources_available"]):
        raise coverage.CoverageError("registered TIGER macOS profile does not match target")
    if pg not in {"16.15", "17.11", "18.6"} or architecture not in {"arm64", "x86_64"}:
        raise coverage.CoverageError("unsupported TIGER macOS target")
    outcomes = {"archive-suite": archive_suite, "static-analysis": static_analysis}
    allowed = {"success": "passed", "failure": "failed", "skipped": "skipped",
               "cancelled": "skipped", "timed_out": "failed"}
    if any(value not in allowed for value in outcomes.values()):
        raise coverage.CoverageError("invalid verification step outcome")
    results = {case: allowed[value] for case, value in outcomes.items()}
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version) or not image_id:
        raise coverage.CoverageError("macOS runner identity is missing")
    env = os.environ if environ is None else environ
    revision, run_id = env.get("GITHUB_SHA", ""), env.get("GITHUB_RUN_ID", "")
    repository, server = env.get("GITHUB_REPOSITORY", ""), env.get("GITHUB_SERVER_URL", "")
    if not coverage.REVISION.fullmatch(revision) or not run_id.isdigit() or not repository or not server:
        raise coverage.CoverageError("GitHub Actions provenance is missing")

    names = {
        "core": f"postgresql-{pg}-{platform}.tar.gz",
        "postgis": f"postgis-{POSTGIS_VERSION}-postgresql-{pg}-{platform}.tar.gz",
        "tiger": f"postgis_tiger_geocoder-{VERSION}-postgresql-{pg}-{platform}.tar.gz",
    }
    paths = {"core": core_dir / names["core"], "postgis": postgis_dir / names["postgis"],
             "tiger": tiger_dir / names["tiger"]}
    hashes = {}
    for key, path in paths.items():
        if path.is_symlink() or not path.is_file():
            raise coverage.CoverageError(f"required archive is missing or not regular: {path.name}")
        hashes[path.name] = sha256(path)
        sidecar = path.with_name(path.name + ".sha256")
        try:
            fields = sidecar.read_text(encoding="utf-8").split()
        except OSError as exc:
            raise coverage.CoverageError(f"missing checksum sidecar for {path.name}") from exc
        if len(fields) < 2 or fields[0].lower() != hashes[path.name] or fields[-1].lstrip("*") != path.name:
            raise coverage.CoverageError(f"checksum sidecar does not match {path.name}")
    expected_target = {"postgresql_version": pg, "platform": "macos", "architecture": architecture}
    postgis_metadata = archive_metadata(paths["postgis"])
    tiger_metadata = archive_metadata(paths["tiger"])
    if (any(postgis_metadata.get(key) != value for key, value in expected_target.items())
            or postgis_metadata.get("project") != "postgis"
            or postgis_metadata.get("version") != POSTGIS_VERSION
            or postgis_metadata.get("core_archive") != {
                "basename": names["core"], "sha256": hashes[names["core"]]}):
        raise coverage.CoverageError("PostGIS metadata does not bind the selected core archive")
    if (any(tiger_metadata.get(key) != value for key, value in expected_target.items())
            or tiger_metadata.get("project") != "postgis_tiger_geocoder"
            or tiger_metadata.get("version") != VERSION
            or tiger_metadata.get("requires") != ["PostGIS"]
            or tiger_metadata.get("source") != {
                "url": "https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-2025.2.tar.gz",
                "sha256": "c33cfbfb40785db8754a36be66060e8d023773e7e1be8fb8a622bb3c48db9f54"}):
        raise coverage.CoverageError("TIGER metadata does not identify its PostGIS prerequisite and source")
    report_path = output.parent / "static-analysis.json"
    probe_path = output.parent / "probe-output.txt"
    reports = {label: sha256(path) for label, path in
               (("static_analysis", report_path), ("probe_output", probe_path)) if path.is_file()}
    if results["static-analysis"] == "passed":
        report = coverage.load_json(report_path)
        if report.get("passed") is not True or report.get("architecture") != architecture:
            raise coverage.CoverageError("static-analysis report does not pass for selected architecture")
        report_archives = report.get("archives")
        if isinstance(report_archives, list):
            report_archives = {item["basename"]: item["sha256"] for item in report_archives}
        if not isinstance(report_archives, dict) or report_archives != hashes:
            raise coverage.CoverageError("static-analysis report is not bound to selected archives")
    if results["archive-suite"] == "passed":
        probe = probe_path.read_text(encoding="utf-8") if probe_path.is_file() else ""
        if probe.count("CREATE EXTENSION") != 3 or not re.search(r"(?m)^DO\s*$", probe):
            raise coverage.CoverageError("archive-suite output does not show the TIGER SQL probe")

    prerequisite = {"project": "PostGIS", "archive": names["postgis"],
                    "version": POSTGIS_VERSION, "sha256": hashes[names["postgis"]]}
    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server.rstrip('/')}/{repository}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    record = {"schema_version": 2, "scope": "publication", "profile_id": profile_id,
              "profile_revision": profile["profile_revision"], "test_cases": CASES,
              "case_results": results, "test_revision": revision, "ci": ci, "outcome": outcome,
              "sha256": hashes[names["tiger"]], "component": "postgis_tiger_geocoder",
              "project": "PostGIS TIGER Geocoder", "version": VERSION, "platform": platform,
              "postgresql_version": pg,
              "assembled_core": {"archive": names["core"], "sha256": hashes[names["core"]], "version": pg},
              "prerequisite_archives": [prerequisite], "reports": reports,
              "environment": {"os": "macos", "os_version": os_version,
                              "architecture": architecture, "clean_system": True,
                              "endpoint": "current", "image_id": image_id,
                              "dependency_check_profile": "macho-system-dependencies-v1",
                              "dependency_checks_passed": results["static-analysis"] == "passed"}}
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    output.mkdir(parents=True, exist_ok=True)
    (output / "verification-record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "archive-hashes.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--postgis", type=Path, required=True)
    parser.add_argument("--tiger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--archive-suite-result", required=True)
    parser.add_argument("--static-analysis-result", required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args()
    try:
        emit(args.root, args.core, args.postgis.parent, args.tiger.parent, args.output,
             args.postgresql_version, args.architecture, args.archive_suite_result,
             args.static_analysis_result, args.os_version, args.image_id)
    except (coverage.CoverageError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"TIGER macOS publication evidence: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
