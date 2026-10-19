#!/usr/bin/env python3
"""Validate and retain evidence for one selected PostGIS Linux target."""

import argparse
from pathlib import Path
import re
import shutil
import sys

import coverage
import emit_extension_publication_records
import linux_core_resolution
from import_linux_publication_run import (
    _case_results, _outcome, _sha256, _sidecar, _static_analysis, _steps,
    _validate_receipt, _validate_record,
)


ARCHITECTURES = {"x86_64", "arm64"}
POSTGIS_VERSION = "3.6.4"
MAX_EVIDENCE_BYTES = 1024 * 1024


def _retain(source, destination):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
        raise coverage.CoverageError(
            f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {source}")
    if destination.exists():
        if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def import_run(root, core_artifact, postgis_artifact, run_id, architecture,
               postgresql_version):
    root = Path(root)
    core_artifact, postgis_artifact = map(Path, (core_artifact, postgis_artifact))
    run_id = str(run_id)
    if (not re.fullmatch(r"[1-9][0-9]*", run_id)
            or architecture not in ARCHITECTURES
            or not re.fullmatch(r"\d+\.\d+", str(postgresql_version))):
        raise coverage.CoverageError(
            "expected numeric run_id, selected PostgreSQL minor, and x86_64 or arm64")
    postgresql_version = str(postgresql_version)
    support = coverage.load_json(root / "support.json")
    releases = coverage.release_snapshot(
        coverage.load_json(root / "support/postgresql-releases.json"), support)
    if postgresql_version not in releases:
        raise coverage.CoverageError(f"PostgreSQL {postgresql_version} is not selected")
    project = support["extensions"].get("PostGIS")
    version_config = project.get("versions", {}).get(POSTGIS_VERSION) if project else None
    if not isinstance(version_config, dict):
        raise coverage.CoverageError("PostGIS 3.6.4 is not declared in support")
    major = int(postgresql_version.split(".", 1)[0])
    if (major < version_config.get("postgresql_minimum_major", 0)
            or major > version_config.get("postgresql_maximum_major", major)):
        raise coverage.CoverageError(f"PostGIS 3.6.4 does not support PostgreSQL {major}")

    platform = f"linux-{architecture}"
    profile_id = f"postgis-publication-linux-{architecture}-{postgresql_version}"
    profile = coverage.verification_profile(root, profile_id)
    if profile["scope"] != "publication" or platform not in profile["platforms"]:
        raise coverage.CoverageError("profile does not match the Linux publication platform")

    core_dir = core_artifact / "pilot"
    postgis_dir = postgis_artifact / "postgis"
    publication = postgis_artifact / "postgis-publication"
    core_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    extension_name = f"postgis-{POSTGIS_VERSION}-postgresql-{postgresql_version}-{platform}.tar.gz"
    core_archive = core_dir / core_name
    extension_archive = postgis_dir / extension_name
    steps_path = publication / "current-steps.json"
    receipt_path = publication / "current-receipt.json"
    records_dir = publication / "records"

    steps = _steps(steps_path, profile)
    if len(profile["case_ids"]) != 1:
        raise coverage.CoverageError("PostGIS publication profile must define one archive suite")
    case_results = _case_results(steps)
    if not core_archive.is_file() or not extension_archive.is_file():
        raise coverage.CoverageError("PostGIS receipt requires exact core and extension archives")
    digests = {}
    for archive in (core_archive, extension_archive):
        digest = _sha256(archive)
        _sidecar(archive, digest)
        digests[archive.name] = digest
    core_resolution = core_dir / "core-resolution.json"
    try:
        linux_core_resolution.validate_resolution(
            core_resolution, core_archive, postgresql_version, architecture)
    except ValueError as exc:
        raise coverage.CoverageError(f"invalid exact PostgreSQL core provenance: {exc}") from exc

    sql_names = project.get("sql_names")
    if (not isinstance(sql_names, list) or len(sql_names) != 4
            or len(set(sql_names)) != 4):
        raise coverage.CoverageError("PostGIS must declare exactly four unique SQL extension names")
    prerequisites = emit_extension_publication_records._metadata(
        extension_archive, "postgis", POSTGIS_VERSION, platform,
        postgresql_version, sql_names)
    if prerequisites != project.get("requires", []):
        raise coverage.CoverageError("PostGIS archive prerequisites do not match declared support")

    receipt = _validate_receipt(
        receipt_path, profile_id, profile, "current", architecture, run_id,
        steps, [extension_name, core_name], digests, postgresql_version,
        "", POSTGIS_VERSION, core_name)
    if receipt is None:
        raise coverage.CoverageError("PostGIS records require a matching target receipt")
    if _outcome(receipt["case_results"]) == "passed" and (
            receipt.get("clean_system") is not True
            or receipt.get("dependency_checks_passed") is not True):
        raise coverage.CoverageError("passed receipt requires a clean system and successful dependency checks")

    expected_components = set(sql_names)
    record_paths = sorted(records_dir.glob("*.json"))
    if len(record_paths) != len(expected_components):
        raise coverage.CoverageError("PostGIS receipt requires exactly four component records")
    records = []
    components = set()
    for path in record_paths:
        record = _validate_record(
            path, support, root, profile_id, profile, "current", platform,
            run_id, steps, digests, core_name, "postgis", receipt,
            postgresql_version, "", POSTGIS_VERSION)
        component = record.get("component")
        if component in components:
            raise coverage.CoverageError(f"duplicate PostGIS component record: {component}")
        components.add(component)
        records.append((path, record))
    if components != expected_components:
        raise coverage.CoverageError("PostGIS records do not cover every declared SQL extension")

    report_path = postgis_dir / "static-analysis/postgis.json"
    report = _static_analysis(
        report_path, architecture, digests,
        _outcome(receipt["case_results"]) == "passed")
    target = (root / "support/evidence" / f"postgis-publication-{run_id}"
              / architecture / postgresql_version)
    copies = [(steps_path, target / steps_path.name),
              (receipt_path, target / receipt_path.name),
              (core_resolution, target / core_resolution.name)]
    copies.extend((path, root / "support/verification" / path.name)
                  for path, _ in records)
    if report is not None:
        copies.append((report, target / "static-analysis" / report.name))
    for source, destination in copies:
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise coverage.CoverageError(
                f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {source}")
        if destination.exists() and (
                destination.is_symlink() or not destination.is_file()
                or destination.read_bytes() != source.read_bytes()):
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        _retain(source, destination)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True,
                        help="extracted artifact root containing pilot/")
    parser.add_argument("--postgis-artifact", type=Path, required=True,
                        help="extracted artifact root containing postgis/ and postgis-publication/")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    parser.add_argument("--postgresql-version", required=True)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(
            args.root, args.core_artifact, args.postgis_artifact, args.run_id,
            args.architecture, args.postgresql_version)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux PostGIS publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
