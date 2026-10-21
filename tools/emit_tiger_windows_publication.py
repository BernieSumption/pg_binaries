#!/usr/bin/env python3
"""Emit archive-bound Windows TIGER publication evidence."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile

import coverage
from license_pointer import verify_archive

PROJECT = "PostGIS TIGER Geocoder"
VERSION = "2025.2"
POSTGIS_VERSION = "3.6.4"
PLATFORM = "windows-x86_64"
POSTGRESQL_VERSIONS = ("16.15", "17.11", "18.6")
CASES = ["archive-suite", "static-analysis"]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_static_report(report, archive_names, hashes):
    expected = [{"basename": name, "sha256": hashes[name]} for name in archive_names]
    if (report.get("outcome") != "passed" or report.get("architecture") != "x86_64"
            or not report.get("inspected_files") or report.get("archives") != expected):
        raise coverage.CoverageError("static analysis report does not bind a passing x86-64 inspection to the exact archives")


def emit(root, core_dir, postgis_dir, tiger_dir, output, steps, os_version, image_id):
    root, core_dir, postgis_dir, tiger_dir, output = map(Path, (root, core_dir, postgis_dir, tiger_dir, output))
    if not isinstance(steps, dict) or set(steps) != set(CASES) or any(v not in {"passed", "failed", "skipped"} for v in steps.values()):
        raise coverage.CoverageError("step results must cover archive-suite and static-analysis")
    candidates = []
    for pg in POSTGRESQL_VERSIONS:
        names = [f"postgresql-{pg}-{PLATFORM}.tar.gz",
                 f"postgis-{POSTGIS_VERSION}-postgresql-{pg}-{PLATFORM}.tar.gz",
                 f"postgis_tiger_geocoder-{VERSION}-postgresql-{pg}-{PLATFORM}.tar.gz"]
        if any((d / n).is_file() for d, n in zip((core_dir, postgis_dir, tiger_dir), names)):
            if not all((d / n).is_file() for d, n in zip((core_dir, postgis_dir, tiger_dir), names)):
                raise coverage.CoverageError(f"incomplete archive set for PostgreSQL {pg}")
            candidates.append((pg, names))
    if len(candidates) != 1:
        raise coverage.CoverageError("archive directories must contain exactly one selected target")
    pg, names = candidates[0]
    profile_id = f"tiger-publication-windows-x86_64-{pg}"
    profile = coverage.verification_profile(root, profile_id)
    if profile["scope"] != "publication" or profile["platforms"] != [PLATFORM] or profile["case_ids"] != CASES or not profile["sources_available"]:
        raise coverage.CoverageError("Windows TIGER publication profile is unavailable or inconsistent")
    paths = [core_dir / names[0], postgis_dir / names[1], tiger_dir / names[2]]
    hashes = {p.name: digest(p) for p in paths}
    for p in paths:
        sidecar = Path(str(p) + ".sha256").read_text().strip().split()
        if len(sidecar) != 2 or sidecar[0].lower() != hashes[p.name] or sidecar[1].lstrip("*") != p.name:
            raise coverage.CoverageError(f"checksum sidecar does not match {p.name}")
    for p, component in zip(paths, ("postgresql", "postgis", "postgis_tiger_geocoder")):
        verify_archive(p, component)
    metadata_by_archive = {}
    for path, metadata_name, project, version, core_bound in (
        (paths[1], "postgis/metadata.json", "PostGIS", POSTGIS_VERSION, True),
        (paths[2], "metadata.json", "postgis_tiger_geocoder", VERSION, False)):
        with tarfile.open(path, "r:gz") as archive:
            members = [m for m in archive.getmembers() if m.name == metadata_name and m.isfile() and m.size <= 1048576]
            if len(members) != 1:
                raise coverage.CoverageError(f"{path.name} requires one bounded {metadata_name}")
            metadata = json.load(archive.extractfile(members[0]))
        metadata_by_archive[path.name] = metadata
        if (metadata.get("project") != project or metadata.get("version") != version
                or metadata.get("postgresql_version") != pg or metadata.get("platform") != "windows"
                or metadata.get("architecture") != "x86_64"):
            raise coverage.CoverageError(f"{path.name} metadata does not match selected target")
        if core_bound and metadata.get("core_archive") != {"basename": paths[0].name, "sha256": hashes[paths[0].name]}:
            raise coverage.CoverageError("PostGIS prerequisite metadata does not bind the selected core")
    identity = json.loads((core_dir / "identity.json").read_text())
    if identity.get("sha256") != hashes[paths[0].name] or identity.get("status") != "checked":
        raise coverage.CoverageError("core identity does not bind the selected archive")
    static_path, probe_path = tiger_dir / "static-analysis.json", tiger_dir / "probe-output.txt"
    static = json.loads(static_path.read_text())
    if metadata_by_archive[names[2]].get("requires") != ["PostGIS"]:
        raise coverage.CoverageError("TIGER archive metadata must declare the PostGIS prerequisite")
    if steps["static-analysis"] == "passed":
        validate_static_report(static, names, hashes)
    if steps["archive-suite"] == "passed":
        probe = probe_path.read_text(errors="replace") if probe_path.is_file() else ""
        if probe.count("CREATE EXTENSION") != 3 or not re.search(r"(?m)^DO\s*$", probe):
            raise coverage.CoverageError("probe output does not show the TIGER SQL checks")
    revision, run_id = os.environ.get("GITHUB_SHA", ""), os.environ.get("GITHUB_RUN_ID", "")
    if not coverage.REVISION.fullmatch(revision) or not run_id.isdigit():
        raise coverage.CoverageError("GitHub Actions provenance is required")
    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    outcome = "failed" if "failed" in steps.values() else "skipped" if "skipped" in steps.values() else "passed"
    receipt = {"schema_version": 1, "profile_id": profile_id, "profile_revision": profile["profile_revision"],
               "test_revision": revision, "project": PROJECT, "version": VERSION,
               "postgresql_version": pg, "architecture": "x86_64", "platform": PLATFORM,
               "endpoint": "current", "case_results": steps, "archives": hashes,
               "extension_archive": paths[2].name,
               "reports": {"static_analysis": digest(static_path), "probe_output": digest(probe_path)},
               "clean_system": True, "dependency_check_profile": "windows-pe-archive-relocation-v1",
               "dependency_checks_passed": steps["static-analysis"] == "passed", "release_eligible": False,
               "environment": {"os": "windows", "os_version": os_version, "architecture": "x86_64", "image_id": image_id}, "ci": ci}
    record = {"schema_version": 2, "scope": "publication", "profile_id": profile_id,
              "profile_revision": profile["profile_revision"], "test_cases": CASES, "case_results": steps,
              "test_revision": revision, "ci": ci, "outcome": outcome, "sha256": hashes[paths[2].name],
              "component": "postgis_tiger_geocoder", "project": PROJECT, "version": VERSION,
              "platform": PLATFORM, "postgresql_version": pg,
              "assembled_core": {"archive": paths[0].name, "sha256": hashes[paths[0].name], "version": pg},
              "prerequisite_archives": [{"project": "PostGIS", "archive": paths[1].name,
                                         "version": POSTGIS_VERSION, "sha256": hashes[paths[1].name]}],
              "release_eligible": False,
              "environment": {"os": "windows", "os_version": os_version, "architecture": "x86_64",
                              "clean_system": True, "endpoint": "current", "image_id": image_id,
                              "dependency_check_profile": receipt["dependency_check_profile"],
                              "dependency_checks_passed": receipt["dependency_checks_passed"]}}
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    output.mkdir(parents=True, exist_ok=True)
    (output / "current-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    (output / "records").mkdir(exist_ok=True)
    (output / "records" / f"postgis_tiger_geocoder-{VERSION}-postgresql-{pg}-{PLATFORM}-current-{run_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--core-archives", type=Path, required=True)
    p.add_argument("--postgis-archives", type=Path, required=True)
    p.add_argument("--tiger-archives", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--steps", type=Path, required=True)
    p.add_argument("--os-version", required=True)
    p.add_argument("--image-id", required=True)
    a = p.parse_args()
    emit(a.root, a.core_archives, a.postgis_archives, a.tiger_archives, a.output,
         json.loads(a.steps.read_text()), a.os_version, a.image_id)


if __name__ == "__main__":
    main()
