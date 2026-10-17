#!/usr/bin/env python3
"""Validate and retain one extracted Linux TIGER publication run."""

import argparse
import gzip
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


def _retain_steps(root, run_id, architecture, step_sources):
    target = root / "support/evidence" / f"tiger-publication-{run_id}" / architecture
    copies = [(source, target / source.name) for source in step_sources]
    for source, destination in copies:
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        _copy(source, destination)
    return [str(destination.relative_to(root)) for _, destination in copies]


def _gzip_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as input_stream, destination.open("wb") as output_stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output_stream, mtime=0) as compressor:
            shutil.copyfileobj(input_stream, compressor)


def _validate_guest(evidence_dir, architecture, core_name, postgis_name, tiger_name,
                    digests, record):
    environment = evidence_dir / "environment.txt"
    checksum_file = evidence_dir / "archive-checksums.sha256"
    full_log = evidence_dir / "full-verifier.log"
    for path in (environment, checksum_file, full_log):
        if not path.is_file():
            raise coverage.CoverageError(f"passed minimum record requires {path}")
    env_text = environment.read_text(encoding="utf-8")
    env_values = {}
    for line in env_text.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            env_values[key] = value
    log_text = full_log.read_text(encoding="utf-8")
    from emit_linux_minimum_pilot_records import parse_archive_checksums
    actual = parse_archive_checksums(checksum_file)
    expected = {name: digests[name] for name in (core_name, postgis_name, tiger_name)}
    if actual != expected:
        raise coverage.CoverageError("guest checksum list does not match the three run archives")
    expected_line = f"PASS: TIGER Geocoder 2025.2 minimum-kernel archive verification"
    if (f"guest_architecture={architecture}" not in log_text.splitlines()
            or not any(line.startswith("guest_kernel=5.15.") for line in log_text.splitlines())
            or not any(line.startswith("guest_os=Ubuntu 22.04") for line in log_text.splitlines())
            or expected_line not in log_text.splitlines()):
        raise coverage.CoverageError("guest log lacks the expected architecture, Linux 5.15 identity, or PASS marker")
    guest_kernel = next(line.split("=", 1)[1] for line in log_text.splitlines()
                        if line.startswith("guest_kernel="))
    if record.get("environment", {}).get("kernel_release") != guest_kernel:
        raise coverage.CoverageError("minimum record kernel does not match guest log")
    if record.get("environment", {}).get("distribution") != next(
            line.split("=", 1)[1] for line in log_text.splitlines()
            if line.startswith("guest_os=")):
        raise coverage.CoverageError("minimum record distribution does not match guest log")
    test_revision = record.get("test_revision")
    if f"test_revision={test_revision}" not in env_text.splitlines():
        raise coverage.CoverageError("guest environment test revision does not match record")
    image_id = record.get("environment", {}).get("image_id", "")
    if (not isinstance(image_id, str) or not image_id.startswith("sha256:")
            or env_values.get("image_sha256") != image_id.removeprefix("sha256:")):
        raise coverage.CoverageError("guest environment image checksum does not match record")


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
    evidence_dir = tiger_artifact / "tiger-qemu" / "evidence"
    record_sources = []
    receipt_sources = []
    step_sources = []
    retained_records = []
    endpoint_data = {}
    for endpoint in ("current", "minimum"):
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

    minimum_record = next((record for record in retained_records
                           if record.get("environment", {}).get("endpoint") == "minimum"
                           and record.get("outcome") == "passed"), None)
    if minimum_record is not None:
        _validate_guest(evidence_dir, architecture, core.name, postgis.name,
                        tiger.name, digests, minimum_record)
    if evidence_dir.exists():
        checksums = evidence_dir / "archive-checksums.sha256"
        if checksums.is_file():
            from emit_linux_minimum_pilot_records import parse_archive_checksums
            actual = parse_archive_checksums(checksums)
            expected = {name: digests[name] for name in (core.name, postgis.name, tiger.name)}
            if actual != expected:
                raise coverage.CoverageError("guest checksum list does not match the three run archives")
        elif any(record.get("environment", {}).get("endpoint") == "minimum"
                 for record in retained_records):
            raise coverage.CoverageError("minimum endpoint record requires guest archive checksum evidence")

    evidence_target = root / "support/evidence" / f"tiger-publication-{run_id}" / architecture
    verification_target = root / "support/verification"
    copies = []
    for source in step_sources + receipt_sources:
        copies.append((source, evidence_target / source.name))
    for relative in ("environment.txt", "archive-checksums.sha256"):
        source = evidence_dir / relative
        if source.is_file():
            copies.append((source, evidence_target / "qemu" / relative))
    full_log = evidence_dir / "full-verifier.log"
    for source in record_sources:
        copies.append((source, verification_target / source.name))
    for source, destination in copies:
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        _copy(source, destination)
    compressed_log = evidence_target / "qemu/full-verifier.log.gz"
    if full_log.is_file():
        evidence_target.mkdir(parents=True, exist_ok=True)
        if compressed_log.exists():
            with gzip.open(compressed_log, "rb") as stream:
                if stream.read() != full_log.read_bytes():
                    raise coverage.CoverageError(f"refusing to replace retained evidence {compressed_log}")
        else:
            _gzip_copy(full_log, compressed_log)
        copies.append((full_log, compressed_log))
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
