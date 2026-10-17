#!/usr/bin/env python3
"""Validate and retain compact core and PostGIS evidence from one Linux run."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import coverage


ARCHITECTURES = {"x86_64", "arm64"}
PG_VERSION = "18.6"
VECTOR_VERSION = "0.8.7"
POSTGIS_VERSION = "3.6.4"


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar(path, digest):
    sidecar = Path(f"{path}.sha256")
    if not sidecar.is_file():
        return
    lines = sidecar.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise coverage.CoverageError(f"{sidecar}: expected exactly one checksum")
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^\s]+)", lines[0])
    if (not match or Path(match.group(2)).name != Path(path).name
            or match.group(1).lower() != digest):
        raise coverage.CoverageError(f"{sidecar}: checksum does not match {Path(path).name}")


def _steps(path, profile):
    data = coverage.load_json(path)
    if (not isinstance(data, dict) or set(data) != set(profile["case_ids"])
            or any(value not in {"success", "failure", "skipped"} for value in data.values())):
        raise coverage.CoverageError(f"{path}: step outcomes do not match the registered profile")
    return data


def _case_results(steps):
    return {case: {"success": "passed", "failure": "failed", "skipped": "skipped"}[value]
            for case, value in steps.items()}


def _outcome(results):
    return ("failed" if "failed" in results.values()
            else "skipped" if "skipped" in results.values() else "passed")


def _retain(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        if destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _validate_receipt(receipt_path, profile_id, profile, endpoint, architecture,
                      run_id, steps, expected_archives, digests, core_name=None):
    if not Path(receipt_path).is_file():
        return None
    receipt = coverage.load_json(receipt_path)
    ci = receipt.get("ci") if isinstance(receipt, dict) else None
    revision = receipt.get("test_revision") if isinstance(receipt, dict) else None
    if (not isinstance(ci, dict) or str(ci.get("run_id")) != run_id
            or ci.get("provider") != "github-actions"
            or not isinstance(ci.get("run_url"), str)
            or not ci["run_url"].startswith("https://github.com/")
            or not ci["run_url"].endswith(f"/actions/runs/{run_id}")
            or any(ci.get(key) != revision for key in
                   ("source_revision", "build_revision", "test_revision"))
            or receipt.get("profile_id") != profile_id
            or receipt.get("profile_revision") not in profile["compatible_profile_revisions"]
            or receipt.get("case_results") != _case_results(steps)
            or receipt.get("endpoint") != endpoint
            or receipt.get("architecture") != architecture
            or receipt.get("test_revision") != ci.get("test_revision")):
        raise coverage.CoverageError(f"{receipt_path}: receipt identity or outcomes do not match this run")
    if (receipt.get("distribution") != "Alpine Linux"
            or not re.fullmatch(r"3\.22(?:\.\d+)?", str(receipt.get("distribution_version", "")))
            or not isinstance(receipt.get("kernel_release"), str)
            or not receipt["kernel_release"]
            or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", str(receipt.get("image_id", "")))):
        raise coverage.CoverageError(f"{receipt_path}: current receipt must identify Alpine 3.22 and its kernel and image")
    archive_claims = receipt.get("archives")
    if not isinstance(archive_claims, dict) or set(archive_claims) != set(expected_archives):
        raise coverage.CoverageError(f"{receipt_path}: archive claims do not match expected archives")
    for name, digest in digests.items():
        if archive_claims.get(name) != digest:
            raise coverage.CoverageError(f"{receipt_path}: archive checksum mismatch for {name}")
    if core_name is not None:
        prerequisites = receipt.get("prerequisite_archives")
        if prerequisites != []:
            raise coverage.CoverageError(f"{receipt_path}: PostGIS must not declare extension prerequisites")
        if receipt.get("project") != "PostGIS" or receipt.get("version") != POSTGIS_VERSION:
            raise coverage.CoverageError(f"{receipt_path}: expected PostGIS 3.6.4")
        if receipt.get("postgresql_version") != PG_VERSION:
            raise coverage.CoverageError(f"{receipt_path}: PostgreSQL build version mismatch")
        if receipt.get("extension_archive") not in expected_archives:
            raise coverage.CoverageError(f"{receipt_path}: extension archive claim is invalid")
    elif receipt.get("postgresql_version") != PG_VERSION:
        raise coverage.CoverageError(f"{receipt_path}: PostgreSQL version mismatch")
    return receipt


def _record_files(directory, run_id):
    if not Path(directory).is_dir():
        return []
    return sorted(path for path in Path(directory).glob(f"*-{run_id}.json") if path.is_file())


def _validate_record(path, support, root, profile_id, profile, endpoint, platform,
                     run_id, steps, digests, core_name, kind, receipt):
    record = coverage.load_json(path)
    coverage.validate_verification_record(record, support, root)
    results = _case_results(steps)
    identity = (record.get("profile_id") == profile_id
                and record.get("profile_revision") in profile["compatible_profile_revisions"]
                and record.get("scope") == "publication"
                and record.get("platform") == platform
                and record.get("postgresql_version") == PG_VERSION
                and record.get("environment", {}).get("endpoint") == endpoint
                and record.get("test_cases") == profile["case_ids"]
                and record.get("case_results") == results
                and record.get("outcome") == _outcome(results)
                and isinstance(record.get("ci"), dict)
                and record["ci"] == receipt.get("ci")
                and str(record["ci"].get("run_id")) == run_id)
    if not identity:
        raise coverage.CoverageError(f"{path}: record identity or outcome does not match its receipt/profile")
    if kind == "core":
        component = record.get("component")
        names = {"postgresql": core_name,
                 "vector": f"pgvector-{VECTOR_VERSION}-postgresql-{PG_VERSION}-{platform}.tar.gz"}
        if component not in names or record.get("version") != (PG_VERSION if component == "postgresql" else VECTOR_VERSION):
            raise coverage.CoverageError(f"{path}: unexpected PostgreSQL publication component")
        archive_name = names[component]
        if record.get("sha256") != digests.get(archive_name):
            raise coverage.CoverageError(f"{path}: archive checksum does not match {archive_name}")
        if component == "vector" and record.get("assembled_core") != {
                "archive": core_name, "sha256": digests.get(core_name), "version": PG_VERSION}:
            raise coverage.CoverageError(f"{path}: assembled core checksum mismatch")
    else:
        project = support["extensions"]["PostGIS"]
        expected = set(project["sql_names"])
        component = record.get("component")
        postgis_name = f"postgis-{POSTGIS_VERSION}-postgresql-{PG_VERSION}-{platform}.tar.gz"
        if (component not in expected or record.get("project") != "PostGIS"
                or record.get("version") != POSTGIS_VERSION
                or record.get("sha256") != digests.get(postgis_name)):
            raise coverage.CoverageError(f"{path}: PostGIS archive or component claim mismatch")
        if record.get("assembled_core") != {
                "archive": core_name, "sha256": digests.get(core_name), "version": PG_VERSION}:
            raise coverage.CoverageError(f"{path}: assembled core checksum mismatch")
        if record.get("prerequisite_archives") != []:
            raise coverage.CoverageError(f"{path}: unexpected PostGIS prerequisites")
    environment = record.get("environment", {})
    receipt_environment = {
        "endpoint": endpoint, "kernel_release": receipt.get("kernel_release"),
        "distribution": receipt.get("distribution"),
        "distribution_version": receipt.get("distribution_version"),
        "architecture": platform.split("-", 1)[1], "clean_system": receipt.get("clean_system"),
        "image_id": receipt.get("image_id"),
        "dependency_check_profile": receipt.get("dependency_check_profile"),
        "dependency_checks_passed": receipt.get("dependency_checks_passed"),
    }
    if any(environment.get(key) != value for key, value in receipt_environment.items()):
        raise coverage.CoverageError(f"{path}: record environment differs from its receipt")
    if kind == "core":
        expected_stem = (f"postgresql-{PG_VERSION}" if record["component"] == "postgresql"
                         else f"pgvector-{VECTOR_VERSION}-postgresql-{PG_VERSION}")
    else:
        expected_stem = f"{record['component']}-{POSTGIS_VERSION}-postgresql-{PG_VERSION}"
    if path.name != f"{expected_stem}-{platform}-{endpoint}-{run_id}.json":
        raise coverage.CoverageError(f"{path}: filename does not match record identity")
    return record


def _copy_tree_files(source, destination, *, limit=1024 * 1024):
    source = Path(source)
    if not source.is_dir():
        return []
    retained = []
    for item in sorted(source.rglob("*")):
        if item.is_file():
            if item.stat().st_size > limit:
                continue
            target = Path(destination) / item.relative_to(source)
            _retain(item, target)
            retained.append(target)
    return retained


def import_run(root, core_artifact, postgis_artifact, run_id, architecture):
    """Validate and retain records, receipts, and compact evidence for a run."""
    root, core_artifact, postgis_artifact = map(Path, (root, core_artifact, postgis_artifact))
    run_id = str(run_id)
    if not re.fullmatch(r"\d+", run_id):
        raise coverage.CoverageError("run_id must contain digits only")
    if architecture not in ARCHITECTURES:
        raise coverage.CoverageError("architecture must be x86_64 or arm64")
    platform = f"linux-{architecture}"
    core_dir = core_artifact / "pilot"
    core_publication = core_dir / "publication"
    postgis_dir = postgis_artifact / "postgis"
    postgis_publication = postgis_artifact / "postgis-publication"
    core_records_dir = core_publication / "records"
    postgis_records_dir = postgis_publication / "records"
    core_name = f"postgresql-{PG_VERSION}-{platform}.tar.gz"
    vector_name = f"pgvector-{VECTOR_VERSION}-postgresql-{PG_VERSION}-{platform}.tar.gz"
    postgis_name = f"postgis-{POSTGIS_VERSION}-postgresql-{PG_VERSION}-{platform}.tar.gz"
    paths = {"core": core_dir / core_name, "vector": core_dir / vector_name,
             "postgis": postgis_dir / postgis_name}
    digests = {}
    for name, path in paths.items():
        if path.is_file():
            digests[path.name] = _sha256(path)
            _sidecar(path, digests[path.name])

    profiles = {}
    steps_by_project = {"core": {}, "postgis": {}}
    receipts = {"core": {}, "postgis": {}}
    for project_name, publication_dir in (("core", core_publication),
                                          ("postgis", postgis_publication)):
        profile_prefix = "linux-publication" if project_name == "core" else "postgis-publication"
        for endpoint in ("current",):
            profile_id = f"{profile_prefix}-{endpoint}-{architecture}"
            profile = coverage.verification_profile(root, profile_id)
            if profile["scope"] != "publication" or platform not in profile["platforms"]:
                raise coverage.CoverageError(f"{profile_id}: not a matching publication profile")
            profiles[project_name, endpoint] = profile
            steps_path = publication_dir / f"{endpoint}-steps.json"
            steps = _steps(steps_path, profile)
            steps_by_project[project_name][endpoint] = (steps_path, steps)
            expected = ([core_name, vector_name] if project_name == "core"
                        else [postgis_name, core_name])
            available_digests = {name: digests[name] for name in expected if name in digests}
            receipt_path = publication_dir / f"{endpoint}-receipt.json"
            receipts[project_name][endpoint] = _validate_receipt(
                receipt_path, profile_id, profile, endpoint, architecture, run_id,
                steps, expected, available_digests,
                core_name if project_name == "postgis" else None)

    has_records = (_record_files(core_records_dir, run_id)
                   or _record_files(postgis_records_dir, run_id))
    has_receipts = any(receipt is not None for group in receipts.values()
                       for receipt in group.values())
    if not all(path.is_file() for path in paths.values()) and not has_records and not has_receipts:
        retained = []
        for project_name, publication_dir in (("core", core_publication),
                                              ("postgis", postgis_publication)):
            target = root / "support/evidence" / (
                f"linux-publication-{run_id}" if project_name == "core"
                else f"postgis-publication-{run_id}") / architecture
            for endpoint in ("current",):
                source = publication_dir / f"{endpoint}-steps.json"
                _retain(source, target / source.name)
                retained.append(str((target / source.name).relative_to(root)))
        return retained

    support = coverage.load_json(root / "support.json")
    records = {"core": {}, "postgis": {}}
    for project_name, directory in (("core", core_records_dir),
                                    ("postgis", postgis_records_dir)):
        files = _record_files(directory, run_id)
        for path in files:
            name = path.name
            endpoint = "current" if "-current-" in name else None
            if endpoint is None:
                raise coverage.CoverageError(f"{path}: record filename has no endpoint")
            if receipts[project_name][endpoint] is None:
                raise coverage.CoverageError(f"{path}: record exists without a matching endpoint receipt")
            required = ([core_name, vector_name] if project_name == "core"
                        else [postgis_name, core_name])
            if any(required_name not in digests for required_name in required):
                raise coverage.CoverageError(f"{path}: record exists but one or more referenced archives are missing")
            profile_id = profiles[project_name, endpoint]["profile_id"]
            record = _validate_record(path, support, root, profile_id,
                                      profiles[project_name, endpoint], endpoint,
                                      platform, run_id, steps_by_project[project_name][endpoint][1],
                                      digests, core_name, project_name,
                                      receipts[project_name][endpoint])
            receipt = receipts[project_name][endpoint]
            if record.get("test_revision") != receipt.get("test_revision"):
                raise coverage.CoverageError(f"{path}: record test revision differs from receipt")
            records[project_name].setdefault(endpoint, []).append((path, record))

    # Existing receipts imply that both archives named by the receipt were emitted.
    for project_name, names in (("core", [core_name, vector_name]),
                                ("postgis", [postgis_name, core_name])):
        for endpoint, receipt in receipts[project_name].items():
            if receipt is not None and any(name not in digests for name in names):
                raise coverage.CoverageError(f"{project_name} {endpoint} receipt exists but a referenced archive is missing")

    for project_name in ("core", "postgis"):
        for endpoint in ("current",):
            if receipts[project_name][endpoint] is None and records[project_name].get(endpoint):
                raise coverage.CoverageError(f"{project_name} records require a matching receipt")
            # If any records exist for an endpoint, the complete declared SQL set is expected.
            if project_name == "postgis" and records[project_name].get(endpoint):
                components = {record["component"] for _, record in records[project_name][endpoint]}
                if components != set(support["extensions"]["PostGIS"]["sql_names"]):
                    raise coverage.CoverageError(f"PostGIS {endpoint} records do not cover every declared SQL name")
            if project_name == "core" and records[project_name].get(endpoint):
                components = {record["component"] for _, record in records[project_name][endpoint]}
                if components != {"postgresql", "vector"}:
                    raise coverage.CoverageError(f"core {endpoint} records do not cover PostgreSQL and pgvector")

    retained = []
    targets = {
        "core": root / "support/evidence" / f"linux-publication-{run_id}" / architecture,
        "postgis": root / "support/evidence" / f"postgis-publication-{run_id}" / architecture,
    }
    for project_name, publication_dir in (("core", core_publication),
                                          ("postgis", postgis_publication)):
        target = targets[project_name]
        for endpoint in ("current",):
            steps_path, _ = steps_by_project[project_name][endpoint]
            _retain(steps_path, target / steps_path.name)
            retained.append(target / steps_path.name)
            receipt_path = publication_dir / f"{endpoint}-receipt.json"
            if receipt_path.is_file():
                _retain(receipt_path, target / receipt_path.name)
                retained.append(target / receipt_path.name)
            for source, record in records[project_name].get(endpoint, []):
                destination = root / "support/verification" / source.name
                _retain(source, destination)
                retained.append(destination)
        symbol_index = (core_dir / "debug-symbols" / "index.json" if project_name == "core"
                        else postgis_dir / "debug-symbols" / "index.json")
        if symbol_index.is_file():
            destination = target / "debug-symbols-index.json"
            _retain(symbol_index, destination)
            retained.append(destination)
        diagnostic_root = core_dir / "diagnostics" if project_name == "core" else None
        if diagnostic_root is not None:
            retained.extend(_copy_tree_files(diagnostic_root, target / "diagnostics"))
    return [str(path.relative_to(root)) for path in retained]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True,
                        help="extracted linux-publication evidence artifact root")
    parser.add_argument("--postgis-artifact", type=Path, required=True,
                        help="extracted postgis-publication evidence artifact root")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    args = parser.parse_args()
    try:
        paths = import_run(args.root, args.core_artifact, args.postgis_artifact,
                           args.run_id, args.architecture)
        print("\n".join(paths))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
