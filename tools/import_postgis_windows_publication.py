#!/usr/bin/env python3
"""Validate and retain PostGIS Windows publication records."""

import argparse
import json
from pathlib import Path
import shutil

import coverage
import emit_postgis_windows_publication as publication


def import_run(root, core_dir, extension_dir, run_id):
    root, core_dir, extension_dir = map(Path, (root, core_dir, extension_dir))
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run ID must be numeric")
    pg_version = publication.selected_version(core_dir, extension_dir)
    profile_name = publication.profile_id(pg_version)
    profile = coverage.verification_profile(root, profile_name)
    pub = extension_dir / "publication"
    receipt = json.loads((pub / "current-receipt.json").read_text())
    if receipt.get("postgresql_version") != pg_version:
        raise coverage.CoverageError("receipt PostgreSQL version differs from the selected archive pair")
    core_name = f"postgresql-{pg_version}-{publication.PLATFORM}.tar.gz"
    ext_name = f"postgis-{publication.VERSION}-postgresql-{pg_version}-{publication.PLATFORM}.tar.gz"
    hashes = {core_name: publication.digest(core_dir / core_name), ext_name: publication.digest(extension_dir / ext_name)}
    if receipt.get("archives") != hashes or receipt.get("profile_id") != profile_name or receipt.get("case_results") != {"archive-suite":"passed","static-analysis":"passed"} or str(receipt.get("ci",{}).get("run_id")) != run_id:
        raise coverage.CoverageError("receipt does not bind passing checks to the final archives")
    expected_reports={"static_analysis":publication.digest(extension_dir/"static-analysis.json"),"pe_dependency_analysis":publication.digest(extension_dir/"pe-dependency-analysis.json"),"probe_output":publication.digest(extension_dir/"probe-output.txt")}
    if receipt.get("reports") != expected_reports:
        raise coverage.CoverageError("receipt report hashes differ from the retained static and SQL evidence")
    records = sorted((pub / "records").glob("*.json"))
    if len(records) != 4:
        raise coverage.CoverageError("expected four PostGIS component records")
    support = coverage.load_json(root / "support.json")
    components = set()
    for path in records:
        record=json.loads(path.read_text()); coverage.validate_verification_record(record,support,root)
        component=record.get("component")
        if component in components or component not in publication.SQL_NAMES or record.get("sha256") != hashes[ext_name] or record.get("assembled_core",{}).get("sha256") != hashes[core_name] or record.get("ci") != receipt.get("ci") or record.get("case_results") != receipt.get("case_results") or record.get("profile_revision") != receipt.get("profile_revision"):
            raise coverage.CoverageError("record identity or archive hashes differ from receipt")
        components.add(component)
    if components != set(publication.SQL_NAMES):
        raise coverage.CoverageError("records do not cover all declared PostGIS SQL components")
    evidence=root/'support/evidence'/f'postgis-windows-publication-{run_id}'/'x86_64'/pg_version
    evidence.mkdir(parents=True,exist_ok=True)
    destinations=[]
    for source in [pub/'current-receipt.json',extension_dir/'static-analysis.json',extension_dir/'pe-dependency-analysis.json',extension_dir/'probe-output.txt',*records]:
        target=evidence/(f"record-{source.name}" if source in records else source.name)
        if target.exists() and target.read_bytes()!=source.read_bytes(): raise coverage.CoverageError(f"refusing to replace retained evidence {target}")
        shutil.copyfile(source,target); destinations.append(target)
    verification=root/'support/verification'; verification.mkdir(parents=True,exist_ok=True)
    for source in records:
        shutil.copyfile(source,verification/source.name)
    return destinations


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); parser.add_argument('--core-archives',type=Path,required=True); parser.add_argument('--archives',type=Path,required=True); parser.add_argument('--run-id',required=True); args=parser.parse_args()
    print('\n'.join(map(str,import_run(args.root,args.core_archives,args.archives,args.run_id))))


if __name__=='__main__': main()
