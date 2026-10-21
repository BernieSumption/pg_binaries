#!/usr/bin/env python3
"""Validate and retain one Windows TIGER publication bundle."""

import argparse
import json
from pathlib import Path
import re
import shutil

import coverage
import emit_tiger_windows_publication as publication


def import_run(root, core_dir, postgis_dir, tiger_dir, run_id):
    root, core_dir, postgis_dir, tiger_dir = map(Path, (root, core_dir, postgis_dir, tiger_dir))
    run_id = str(run_id)
    if not re.fullmatch(r"\d+", run_id):
        raise coverage.CoverageError("run ID must be numeric")
    targets = []
    for pg in publication.POSTGRESQL_VERSIONS:
        names = [f"postgresql-{pg}-{publication.PLATFORM}.tar.gz",
                 f"postgis-{publication.POSTGIS_VERSION}-postgresql-{pg}-{publication.PLATFORM}.tar.gz",
                 f"postgis_tiger_geocoder-{publication.VERSION}-postgresql-{pg}-{publication.PLATFORM}.tar.gz"]
        if any((d / n).is_file() for d, n in zip((core_dir, postgis_dir, tiger_dir), names)):
            if not all((d / n).is_file() for d, n in zip((core_dir, postgis_dir, tiger_dir), names)):
                raise coverage.CoverageError(f"incomplete archive set for PostgreSQL {pg}")
            targets.append((pg, names))
    if len(targets) != 1:
        raise coverage.CoverageError("bundle must contain exactly one selected archive set")
    pg, names = targets[0]
    pub = tiger_dir / "publication"
    receipt = json.loads((pub / "current-receipt.json").read_text())
    record_path = pub / "records" / f"postgis_tiger_geocoder-{publication.VERSION}-postgresql-{pg}-{publication.PLATFORM}-current-{run_id}.json"
    record = json.loads(record_path.read_text())
    profile = coverage.verification_profile(root, f"tiger-publication-windows-x86_64-{pg}")
    if (receipt.get("profile_id") != profile["profile_id"]
            or receipt.get("profile_revision") not in profile["compatible_profile_revisions"]
            or receipt.get("postgresql_version") != pg
            or str(receipt.get("ci", {}).get("run_id")) != run_id
            or receipt.get("case_results") != {"archive-suite": "passed", "static-analysis": "passed"}):
        raise coverage.CoverageError("receipt does not bind passing checks to this run and target")
    paths = [core_dir / names[0], postgis_dir / names[1], tiger_dir / names[2]]
    hashes = {p.name: publication.digest(p) for p in paths}
    if receipt.get("archives") != hashes:
        raise coverage.CoverageError("receipt archive hashes differ from transferred archives")
    static, probe = tiger_dir / "static-analysis.json", tiger_dir / "probe-output.txt"
    if receipt.get("reports") != {"static_analysis": publication.digest(static), "probe_output": publication.digest(probe)}:
        raise coverage.CoverageError("receipt report hashes differ from retained static and probe evidence")
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    if (record.get("ci") != receipt.get("ci") or record.get("profile_revision") != receipt.get("profile_revision")
            or record.get("case_results") != receipt.get("case_results")
            or record.get("sha256") != hashes[names[2]]
            or record.get("assembled_core") != {"archive": names[0], "sha256": hashes[names[0]], "version": pg}
            or record.get("prerequisite_archives") != [{"project": "PostGIS", "archive": names[1],
                                                       "version": publication.POSTGIS_VERSION, "sha256": hashes[names[1]]}]):
        raise coverage.CoverageError("record identity or archive hashes differ from receipt")
    evidence = root / "support/evidence" / f"tiger-windows-publication-{run_id}" / "x86_64" / pg
    sources = [pub / "current-receipt.json", record_path, static, probe]
    destinations = [evidence / "current-receipt.json", evidence / f"record-{record_path.name}", evidence / static.name, evidence / probe.name]
    for source, destination in zip(sources, destinations):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in zip(sources, destinations):
        shutil.copyfile(source, destination)
    verification = root / "support/verification"
    verification.mkdir(parents=True, exist_ok=True)
    destination = verification / record_path.name
    if destination.exists() and destination.read_bytes() != record_path.read_bytes():
        raise coverage.CoverageError(f"refusing to replace retained verification record {destination}")
    shutil.copyfile(record_path, destination)
    return destinations + [destination]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--core-archives", type=Path, required=True)
    p.add_argument("--postgis-archives", type=Path, required=True)
    p.add_argument("--tiger-archives", type=Path, required=True)
    p.add_argument("--run-id", required=True)
    a = p.parse_args()
    print("\n".join(map(str, import_run(a.root, a.core_archives, a.postgis_archives, a.tiger_archives, a.run_id))))


if __name__ == "__main__":
    main()
