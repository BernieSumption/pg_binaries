#!/usr/bin/env python3
"""Validate and retain one selected macOS TIGER publication run."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import coverage

VERSION = "2025.2"
MAX_EVIDENCE_BYTES = 1024 * 1024


def _read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_EVIDENCE_BYTES:
        raise coverage.CoverageError(f"expected bounded regular JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"invalid evidence JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"evidence must be a JSON object: {path}")
    return value


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _retain(source, destination):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
        raise coverage.CoverageError(f"evidence must be a bounded regular file: {source}")
    if destination.exists():
        if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def import_run(root, artifact, run_id, pg_version, architecture, retain_root=None):
    root, artifact = Path(root), Path(artifact)
    retain_root = root if retain_root is None else Path(retain_root)
    run_id = str(run_id)
    if not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise coverage.CoverageError("run_id must be numeric")
    if pg_version not in {"16.15", "17.11", "18.6"} or architecture not in {"arm64", "x86_64"}:
        raise coverage.CoverageError("unsupported TIGER macOS publication target")
    platform = f"macos-{architecture}"
    profile_id = f"tiger-publication-macos-{architecture}-{pg_version}"
    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or profile["platforms"] != [platform]
            or profile["case_ids"] != ["archive-suite", "static-analysis"]):
        raise coverage.CoverageError("registered profile does not match selected TIGER target")

    core_name = f"postgresql-{pg_version}-{platform}.tar.gz"
    postgis_name = f"postgis-3.6.4-postgresql-{pg_version}-{platform}.tar.gz"
    tiger_name = f"postgis_tiger_geocoder-{VERSION}-postgresql-{pg_version}-{platform}.tar.gz"
    core = artifact / "core" / core_name
    postgis = artifact / "verification/postgis" / postgis_name
    tiger = artifact / "output" / tiger_name
    paths = {core_name: core, postgis_name: postgis, tiger_name: tiger}
    digests = {}
    for name, path in paths.items():
        if path.is_symlink() or not path.is_file():
            raise coverage.CoverageError(f"exact archive is missing: {name}")
        digests[name] = _sha256(path)
        sidecar = path.with_name(path.name + ".sha256")
        if sidecar.is_symlink() or not sidecar.is_file():
            raise coverage.CoverageError(f"missing checksum sidecar for {name}")
        if sidecar.read_text(encoding="utf-8").split() != [digests[name], name]:
            raise coverage.CoverageError(f"checksum sidecar does not match {name}")

    publication = artifact / "verification/publication"
    record = _read_json(publication / "verification-record.json")
    hashes = _read_json(publication / "archive-hashes.json")
    if hashes != digests:
        raise coverage.CoverageError("emitted archive hashes differ from downloaded archive bytes")
    ci = record.get("ci")
    if (record.get("profile_id") != profile_id
            or record.get("profile_revision") not in profile["compatible_profile_revisions"]
            or record.get("postgresql_version") != pg_version
            or record.get("platform") != platform
            or record.get("component") != "postgis_tiger_geocoder"
            or record.get("project") != "PostGIS TIGER Geocoder"
            or record.get("version") != VERSION
            or record.get("sha256") != digests[tiger_name]
            or record.get("assembled_core") != {"archive": core_name, "sha256": digests[core_name], "version": pg_version}
            or record.get("prerequisite_archives") != [{"project": "PostGIS", "archive": postgis_name,
                "version": "3.6.4", "sha256": digests[postgis_name]}]
            or not isinstance(ci, dict) or str(ci.get("run_id")) != run_id):
        raise coverage.CoverageError("verification record does not bind the selected run and archives")
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)

    report_paths = {"static_analysis": artifact / "verification/static-analysis.json",
                    "probe_output": artifact / "verification/probe-output.txt"}
    reports = record.get("reports")
    if not isinstance(reports, dict) or set(reports) != set(report_paths):
        raise coverage.CoverageError("verification record report set is incomplete")
    for name, path in report_paths.items():
        if path.is_symlink() or not path.is_file() or _sha256(path) != reports[name]:
            raise coverage.CoverageError(f"retained report does not match verification record: {name}")
    static = _read_json(report_paths["static_analysis"])
    static_archives = static.get("archives")
    if isinstance(static_archives, list):
        static_archives = {item["basename"]: item["sha256"] for item in static_archives}
    if not isinstance(static_archives, dict) or static_archives != digests:
        raise coverage.CoverageError("static-analysis report does not bind all three archives")

    evidence_dir = retain_root / "support/evidence" / f"tiger-macos-publication-{run_id}" / architecture / pg_version
    for name, source in report_paths.items():
        destination = "static-analysis.json" if name == "static_analysis" else "probe-output.txt"
        _retain(source, evidence_dir / destination)
    _retain(publication / "archive-hashes.json", evidence_dir / "archive-hashes.json")
    record_path = retain_root / "support/verification" / (
        f"postgis_tiger_geocoder-{VERSION}-postgresql-{pg_version}-{platform}-current-{run_id}.json")
    _retain(publication / "verification-record.json", record_path)
    return [str((evidence_dir / name).relative_to(retain_root)) for name in
            ("static-analysis.json", "probe-output.txt", "archive-hashes.json")] + [str(record_path.relative_to(retain_root))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--architecture", required=True)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.artifact, args.run_id,
                                   args.postgresql_version, args.architecture)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"macOS TIGER publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
