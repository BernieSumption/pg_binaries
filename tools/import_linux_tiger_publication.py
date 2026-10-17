#!/usr/bin/env python3
"""Validate and retain one extracted Linux TIGER publication run."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import coverage


ARCHITECTURES = {"x86_64", "arm64"}
PROJECT = "PostGIS TIGER Geocoder"
VERSION = "2025.2"
PG_VERSION = "18.6"


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar(path, digest):
    sidecar = path.with_name(path.name + ".sha256")
    try:
        text = sidecar.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise coverage.CoverageError(f"missing checksum sidecar {sidecar}: {exc}") from exc
    if text != f"{digest}  {path.name}":
        raise coverage.CoverageError(f"checksum sidecar does not match {path.name}")


def _steps(path):
    data = coverage.load_json(path)
    if (not isinstance(data, dict) or not data
            or any(not isinstance(name, str) or not name
                   or result not in {"success", "failure", "skipped"}
                   for name, result in data.items())):
        raise coverage.CoverageError(f"{path}: expected step outcomes success, failure, or skipped")
    return data


def _copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
        return
    shutil.copyfile(source, destination)


def _static_analysis(path, architecture, archives, required):
    if not path.is_file():
        if required:
            raise coverage.CoverageError(f"{path}: passed publication requires a static-analysis report")
        return None
    report = coverage.load_json(path)
    if not required and isinstance(report, dict) and report.get("outcome") == "failed":
        return None
    claims = report.get("archives") if isinstance(report, dict) else None
    if (not isinstance(report, dict) or report.get("outcome") != "passed"
            or report.get("architecture") != architecture
            or not isinstance(report.get("files"), list) or not report["files"]
            or any(not isinstance(item, dict) or not isinstance(item.get("path"), str)
                   or not item["path"] for item in report["files"])
            or not isinstance(claims, list)
            or any(not isinstance(item, dict) or set(item) != {"basename", "sha256"}
                   or not isinstance(item["basename"], str)
                   or not re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"])) for item in claims)):
        raise coverage.CoverageError(f"{path}: invalid static-analysis report")
    actual = {item["basename"]: item["sha256"] for item in claims}
    if len(actual) != len(claims) or actual != archives:
        raise coverage.CoverageError(f"{path}: static-analysis archives do not match publication archives")
    return path


def _retain_steps(root, run_id, architecture, step_sources):
    target = root / "support/evidence" / f"tiger-publication-{run_id}" / architecture
    copies = [(source, target / source.name) for source in step_sources]
    for source, destination in copies:
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        _copy(source, destination)
    return [str(destination.relative_to(root)) for _, destination in copies]


def import_run(root, core_artifact, postgis_artifact, tiger_artifact, run_id, architecture):
    """Validate a run bundle, then retain its TIGER records and compact evidence."""
    root, core_artifact, postgis_artifact, tiger_artifact = map(
        Path, (root, core_artifact, postgis_artifact, tiger_artifact))
    if not re.fullmatch(r"\d+", str(run_id)):
        raise coverage.CoverageError("run_id must contain digits only")
    if architecture not in ARCHITECTURES:
        raise coverage.CoverageError("architecture must be x86_64 or arm64")

    platform = f"linux-{architecture}"
    core_dir = core_artifact / "pilot"
    postgis_dir = postgis_artifact / "postgis"
    tiger_dir = tiger_artifact / "tiger"
    publication_dir = tiger_artifact / "tiger-publication"
    records_dir = publication_dir / "records"
    record_sources = []
    receipt_sources = []
    step_sources = []
    retained_records = []
    endpoint_data = {}
    for endpoint in ("current",):
        profile_id = f"tiger-publication-{endpoint}-{architecture}"
        profile = coverage.verification_profile(root, profile_id)
        if profile["scope"] != "publication" or platform not in profile["platforms"]:
            raise coverage.CoverageError(f"{profile_id}: not a matching publication profile")
        steps_path = publication_dir / f"{endpoint}-steps.json"
        steps = _steps(steps_path)
        if set(steps) != set(profile["case_ids"]):
            raise coverage.CoverageError(f"{steps_path}: step names do not match the registered profile")
        step_sources.append(steps_path)
        endpoint_data[endpoint] = {"profile_id": profile_id, "profile": profile, "steps": steps}

        receipt_path = publication_dir / f"{endpoint}-receipt.json"
        if receipt_path.is_file():
            receipt = coverage.load_json(receipt_path)
            receipt_ci = receipt.get("ci") if isinstance(receipt, dict) else None
            if (not isinstance(receipt_ci, dict) or receipt_ci.get("run_id") != str(run_id)
                    or receipt.get("profile_id") != profile_id
                    or receipt.get("profile_revision") not in profile["compatible_profile_revisions"]
                    or receipt.get("case_results") != {
                        key: {"success": "passed", "failure": "failed", "skipped": "skipped"}[value]
                        for key, value in steps.items()}):
                raise coverage.CoverageError(f"{receipt_path}: receipt does not match run and step outcomes")
            if (receipt.get("distribution") != "Alpine Linux"
                    or not re.fullmatch(r"3\.22(?:\.\d+)?", str(receipt.get("distribution_version", "")))
                    or not isinstance(receipt.get("kernel_release"), str)
                    or not receipt["kernel_release"]
                    or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", str(receipt.get("image_id", "")))):
                raise coverage.CoverageError(f"{receipt_path}: current receipt must identify Alpine 3.22 and its kernel and image")
            endpoint_data[endpoint]["receipt"] = receipt
            receipt_sources.append(receipt_path)

    core = core_dir / f"postgresql-{PG_VERSION}-{platform}.tar.gz"
    postgis = postgis_dir / f"postgis-3.6.4-postgresql-{PG_VERSION}-{platform}.tar.gz"
    tiger = tiger_dir / f"postgis_tiger_geocoder-{VERSION}-postgresql-{PG_VERSION}-{platform}.tar.gz"
    archive_paths = (core, postgis, tiger)
    if not all(path.is_file() for path in archive_paths):
        existing_records = [records_dir / (
            f"postgis_tiger_geocoder-{VERSION}-postgresql-{PG_VERSION}-{platform}-{endpoint}-{run_id}.json")
            for endpoint in endpoint_data]
        if any(path.is_file() for path in existing_records):
            raise coverage.CoverageError("TIGER records exist but one or more referenced archives are missing")
        # The workflow emits raw outcomes even when it cannot assemble all archives.
        return _retain_steps(root, run_id, architecture, step_sources)
    digests = {}
    for path in archive_paths:
        digests[path.name] = _sha256(path)
        _sidecar(path, digests[path.name])

    report_path = tiger_dir / "static-analysis/tiger.json"
    passed = any(data.get("receipt", {}).get("case_results")
                 and all(value == "passed" for value in data["receipt"]["case_results"].values())
                 for data in endpoint_data.values()) or any(
                     coverage.load_json(path).get("outcome") == "passed"
                     for path in records_dir.glob(f"*-{run_id}.json") if path.is_file())
    report = _static_analysis(report_path, architecture,
                              digests, passed)

    support = coverage.load_json(root / "support.json")
    for endpoint, data in endpoint_data.items():
        profile_id = data["profile_id"]
        profile = data["profile"]
        steps = data["steps"]
        record_path = records_dir / (
            f"postgis_tiger_geocoder-{VERSION}-postgresql-{PG_VERSION}-{platform}-{endpoint}-{run_id}.json")
        if not record_path.exists():
            continue
        record = coverage.load_json(record_path)
        coverage.validate_verification_record(record, support, root)
        if (record.get("profile_id") != profile_id
                or record.get("profile_revision") not in profile["compatible_profile_revisions"]
                or record.get("platform") != platform
                or record.get("component") != "postgis_tiger_geocoder"
                or record.get("project") != PROJECT or record.get("version") != VERSION
                or record.get("postgresql_version") != PG_VERSION
                or not isinstance(record.get("ci"), dict)
                or record["ci"].get("run_id") != str(run_id)
                or record.get("environment", {}).get("endpoint") != endpoint
                or record.get("outcome") != (
                    "failed" if "failure" in steps.values()
                    else "skipped" if "skipped" in steps.values() else "passed")):
            raise coverage.CoverageError(f"{record_path}: record identity or outcome does not match the run")
        receipt = data.get("receipt")
        if receipt is not None:
            environment = record.get("environment", {})
            if any(environment.get(key) != receipt.get(value)
                   for key, value in (("kernel_release", "kernel_release"),
                                      ("distribution", "distribution"),
                                      ("distribution_version", "distribution_version"),
                                      ("image_id", "image_id"))):
                raise coverage.CoverageError(f"{record_path}: environment differs from its Alpine receipt")
        if record.get("sha256") != digests[tiger.name]:
            raise coverage.CoverageError(f"{record_path}: TIGER archive checksum mismatch")
        if record.get("assembled_core") != {
                "archive": core.name, "sha256": digests[core.name], "version": PG_VERSION}:
            raise coverage.CoverageError(f"{record_path}: assembled core checksum mismatch")
        prerequisites = record.get("prerequisite_archives")
        if prerequisites != [{
                "project": "PostGIS", "archive": postgis.name,
                "version": "3.6.4", "sha256": digests[postgis.name]}]:
            raise coverage.CoverageError(f"{record_path}: prerequisite PostGIS checksum mismatch")
        record_sources.append(record_path)
        retained_records.append(record)

    evidence_target = root / "support/evidence" / f"tiger-publication-{run_id}" / architecture
    verification_target = root / "support/verification"
    copies = []
    for source in step_sources + receipt_sources:
        copies.append((source, evidence_target / source.name))
    for source in record_sources:
        copies.append((source, verification_target / source.name))
    if report is not None:
        copies.append((report, evidence_target / "static-analysis" / report.name))
    for source, destination in copies:
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        _copy(source, destination)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True,
                        help="extracted linux-publication evidence artifact root")
    parser.add_argument("--postgis-artifact", type=Path, required=True,
                        help="extracted postgis-publication evidence artifact root")
    parser.add_argument("--tiger-artifact", type=Path, required=True,
                        help="extracted tiger-publication evidence artifact root")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    args = parser.parse_args()
    try:
        paths = import_run(args.root, args.core_artifact, args.postgis_artifact,
                           args.tiger_artifact, args.run_id, args.architecture)
        print("\n".join(paths))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux TIGER publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
