#!/usr/bin/env python3
"""Create PostGIS Windows publication records bound to final archive bytes."""

import hashlib
import json
import os
from pathlib import Path
import argparse
import tarfile

import coverage
from license_pointer import verify_archive

VERSION = "3.6.4"
SUPPORTED_PG_VERSIONS = ("15.19", "16.15", "17.11", "18.6")
PLATFORM = "windows-x86_64"
PROFILE_PREFIX = "postgis-publication-windows-x86_64-"
SQL_NAMES = ["postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology"]
CASES = ["archive-suite", "static-analysis"]


def profile_id(pg_version):
    if pg_version not in SUPPORTED_PG_VERSIONS:
        raise coverage.CoverageError(f"unsupported PostgreSQL target: {pg_version}")
    return PROFILE_PREFIX + pg_version


def selected_version(core_dir, extension_dir):
    core_dir, extension_dir = Path(core_dir), Path(extension_dir)
    matches = []
    for pg_version in SUPPORTED_PG_VERSIONS:
        core = core_dir / f"postgresql-{pg_version}-{PLATFORM}.tar.gz"
        extension = extension_dir / f"postgis-{VERSION}-postgresql-{pg_version}-{PLATFORM}.tar.gz"
        if core.is_file() or extension.is_file():
            if not core.is_file() or not extension.is_file():
                raise coverage.CoverageError(f"incomplete PostgreSQL {pg_version} archive pair")
            matches.append(pg_version)
    if len(matches) != 1:
        raise coverage.CoverageError("input directories must contain exactly one matching PostgreSQL core and PostGIS archive pair")
    return matches[0]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def archive_metadata(extension):
    with tarfile.open(extension, "r:gz") as archive:
        matches = [m for m in archive.getmembers() if m.name == "metadata.json" and m.isfile() and m.size <= 1048576]
        if len(matches) != 1:
            raise coverage.CoverageError("PostGIS archive requires one bounded metadata.json")
        return json.load(archive.extractfile(matches[0]))


def validate_archive_metadata(metadata, pg_version, core_name, core_sha256):
    if (metadata.get("project") != "PostGIS" or metadata.get("version") != VERSION
            or metadata.get("postgresql_version") != pg_version or metadata.get("platform") != "windows"
            or metadata.get("architecture") != "x86_64" or metadata.get("sql_names") != SQL_NAMES
            or metadata.get("requires") != [] or metadata.get("configuration_prerequisites") != []
            or metadata.get("runtime_prerequisites") != []
            or metadata.get("core_archive") != {"basename": core_name, "sha256": core_sha256}
            or metadata.get("release_eligible") is not False):
        raise coverage.CoverageError("PostGIS archive metadata does not bind this selected core")


def emit(root, core_dir, extension_dir, output, steps, os_version, image_id):
    root, core_dir, extension_dir, output = map(Path, (root, core_dir, extension_dir, output))
    pg_version = selected_version(core_dir, extension_dir)
    profile_name = profile_id(pg_version)
    if set(steps) != set(CASES) or any(v not in {"passed", "failed", "skipped"} for v in steps.values()):
        raise coverage.CoverageError("step results must cover archive-suite and static-analysis")
    profile = coverage.verification_profile(root, profile_name)
    if profile["scope"] != "publication" or profile["platforms"] != [PLATFORM] or profile["case_ids"] != CASES or not profile["sources_available"]:
        raise coverage.CoverageError("PostGIS Windows publication profile is unavailable or inconsistent")
    core_name = f"postgresql-{pg_version}-{PLATFORM}.tar.gz"
    ext_name = f"postgis-{VERSION}-postgresql-{pg_version}-{PLATFORM}.tar.gz"
    core, extension = core_dir / core_name, extension_dir / ext_name
    hashes = {core_name: digest(core), ext_name: digest(extension)}
    for path in (core, extension):
        sidecar = Path(str(path) + ".sha256").read_text().strip().split()
        if len(sidecar) != 2 or sidecar[0].lower() != hashes[path.name] or sidecar[1].lstrip("*") != path.name:
            raise coverage.CoverageError(f"checksum sidecar does not match {path.name}")
    verify_archive(core, "postgresql")
    verify_archive(extension, "postgis")
    metadata = archive_metadata(extension)
    validate_archive_metadata(metadata, pg_version, core_name, hashes[core_name])
    static = json.loads((extension_dir / "static-analysis.json").read_text())
    pe_path = extension_dir / "pe-dependency-analysis.json"
    pe = json.loads(pe_path.read_text())
    if steps["static-analysis"] == "passed" and (static.get("passed") is not True or static.get("architecture") != "x86_64" or not static.get("inspected_files") or static.get("pe_dependency_analysis_sha256") != digest(pe_path) or pe.get("outcome") != "passed" or static.get("archives") != [{"basename": core_name, "sha256": hashes[core_name]}, {"basename": ext_name, "sha256": hashes[ext_name]}]):
        raise coverage.CoverageError("static analysis does not cover the exact final archives")
    revision, run_id = os.environ.get("GITHUB_SHA", ""), os.environ.get("GITHUB_RUN_ID", "")
    if not coverage.REVISION.fullmatch(revision) or not run_id.isdigit():
        raise coverage.CoverageError("GitHub Actions provenance is required")
    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    outcome = "failed" if "failed" in steps.values() else "skipped" if "skipped" in steps.values() else "passed"
    receipt = {"schema_version": 1, "profile_id": profile_name, "profile_revision": profile["profile_revision"],
               "test_revision": revision, "project": "PostGIS", "version": VERSION,
               "postgresql_version": pg_version, "architecture": "x86_64", "platform": PLATFORM,
               "endpoint": "current", "case_results": steps, "archives": hashes,
               "extension_archive": ext_name, "reports": {"static_analysis": digest(extension_dir / "static-analysis.json"), "pe_dependency_analysis": digest(pe_path), "probe_output": digest(extension_dir / "probe-output.txt")},
               "clean_system": True, "dependency_check_profile": "windows-pe-archive-relocation-v1",
               "dependency_checks_passed": steps["static-analysis"] == "passed",
               "release_eligible": False, "core_status": metadata.get("core_status"),
               "environment": {"os": "windows", "os_version": os_version, "architecture": "x86_64", "image_id": image_id}, "ci": ci}
    output.mkdir(parents=True, exist_ok=True)
    (output / "current-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    for component in SQL_NAMES:
        record = {"schema_version": 2, "scope": "publication", "profile_id": profile_name,
                  "profile_revision": profile["profile_revision"], "test_cases": CASES,
                  "case_results": steps, "test_revision": revision, "ci": ci, "outcome": outcome,
                  "sha256": hashes[ext_name], "component": component, "project": "PostGIS",
                  "version": VERSION, "platform": PLATFORM, "postgresql_version": pg_version,
                  "assembled_core": {"archive": core_name, "sha256": hashes[core_name], "version": pg_version},
                  "prerequisite_archives": [], "release_eligible": False, "core_status": metadata.get("core_status"),
                  "environment": {"os": "windows", "os_version": os_version,
                  "architecture": "x86_64", "clean_system": True, "endpoint": "current", "image_id": image_id,
                  "dependency_check_profile": receipt["dependency_check_profile"],
                  "dependency_checks_passed": receipt["dependency_checks_passed"]}}
        coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
        (output / "records").mkdir(exist_ok=True)
        path = output / "records" / f"postgis-{VERSION}-{component}-postgresql-{pg_version}-{PLATFORM}-current-{run_id}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=Path, required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args()
    steps = json.loads(args.steps.read_text())
    emit(args.root, args.core_archives, args.archives, args.output, steps,
         args.os_version, args.image_id)


if __name__ == "__main__":
    main()
