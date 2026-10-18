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
DEFAULT_PG_VERSION = "18.6"


def _selected_extension_version(support, releases, project_name, postgresql_version, platform):
    """Resolve the unique selected version of a project for one exact target."""
    _, targets = coverage.expected_targets(support, releases)
    project = support["extensions"][project_name]
    versions_by_name = {
        name: {version for target_name, version, pg_version, target_platform in targets
               if target_name == name and pg_version == postgresql_version
               and target_platform == platform}
        for name in project["sql_names"]
    }
    unique_versions = set.union(*versions_by_name.values()) if versions_by_name else set()
    if (not unique_versions
            or any(versions != unique_versions for versions in versions_by_name.values())
            or len(unique_versions) != 1):
        raise coverage.CoverageError(
            f"{project_name} must have exactly one selected version for PostgreSQL "
            f"{postgresql_version} on {platform}")
    return next(iter(unique_versions))


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
                      run_id, steps, expected_archives, digests, postgresql_version,
                      vector_version, postgis_version, core_name=None):
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
        if receipt.get("project") != "PostGIS" or receipt.get("version") != postgis_version:
            raise coverage.CoverageError(f"{receipt_path}: expected PostGIS {postgis_version}")
        if receipt.get("postgresql_version") != postgresql_version:
            raise coverage.CoverageError(f"{receipt_path}: PostgreSQL build version mismatch")
        if receipt.get("extension_archive") not in expected_archives:
            raise coverage.CoverageError(f"{receipt_path}: extension archive claim is invalid")
    elif receipt.get("postgresql_version") != postgresql_version:
        raise coverage.CoverageError(f"{receipt_path}: PostgreSQL version mismatch")
    return receipt


def _record_files(directory, run_id):
    if not Path(directory).is_dir():
        return []
    return sorted(path for path in Path(directory).glob(f"*-{run_id}.json") if path.is_file())


def _validate_record(path, support, root, profile_id, profile, endpoint, platform,
                     run_id, steps, digests, core_name, kind, receipt, postgresql_version,
                     vector_version, postgis_version):
    record = coverage.load_json(path)
    coverage.validate_verification_record(record, support, root)
    results = _case_results(steps)
    identity = (record.get("profile_id") == profile_id
                and record.get("profile_revision") in profile["compatible_profile_revisions"]
                and record.get("scope") == "publication"
                and record.get("platform") == platform
                and record.get("postgresql_version") == postgresql_version
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
                 "vector": f"pgvector-{vector_version}-postgresql-{postgresql_version}-{platform}.tar.gz"}
        if component not in names or record.get("version") != (postgresql_version if component == "postgresql" else vector_version):
            raise coverage.CoverageError(f"{path}: unexpected PostgreSQL publication component")
        archive_name = names[component]
        if record.get("sha256") != digests.get(archive_name):
            raise coverage.CoverageError(f"{path}: archive checksum does not match {archive_name}")
        if component == "vector" and record.get("assembled_core") != {
                "archive": core_name, "sha256": digests.get(core_name), "version": postgresql_version}:
            raise coverage.CoverageError(f"{path}: assembled core checksum mismatch")
    else:
        project = support["extensions"]["PostGIS"]
        expected = set(project["sql_names"])
        component = record.get("component")
        postgis_name = f"postgis-{postgis_version}-postgresql-{postgresql_version}-{platform}.tar.gz"
        if (component not in expected or record.get("project") != "PostGIS"
                or record.get("version") != postgis_version
                or record.get("sha256") != digests.get(postgis_name)):
            raise coverage.CoverageError(f"{path}: PostGIS archive or component claim mismatch")
        if record.get("assembled_core") != {
                "archive": core_name, "sha256": digests.get(core_name), "version": postgresql_version}:
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
        expected_stem = (f"postgresql-{postgresql_version}" if record["component"] == "postgresql"
                         else f"pgvector-{vector_version}-postgresql-{postgresql_version}")
    else:
        expected_stem = f"{record['component']}-{postgis_version}-postgresql-{postgresql_version}"
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


def _static_analysis(path, architecture, archives, required):
    path = Path(path)
    if not path.is_file():
        if required:
            raise coverage.CoverageError(f"{path}: passed publication requires a static-analysis report")
        return None
    report = coverage.load_json(path)
    if not required and isinstance(report, dict) and report.get("outcome") == "failed":
        return None
    if (not isinstance(report, dict) or report.get("outcome") != "passed"
            or report.get("architecture") != architecture
            or not isinstance(report.get("files"), list) or not report["files"]
            or any(not isinstance(item, dict) or not isinstance(item.get("path"), str)
                   or not item["path"] for item in report["files"])
            or not isinstance(report.get("archives"), list)):
        raise coverage.CoverageError(f"{path}: invalid static-analysis report")
    claims = report["archives"]
    if any(not isinstance(item, dict) or set(item) != {"basename", "sha256"}
           or not isinstance(item["basename"], str)
           or not re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"])) for item in claims):
        raise coverage.CoverageError(f"{path}: invalid static-analysis archive claims")
    expected = {name: digest for name, digest in archives.items()}
    actual = {item["basename"]: item["sha256"] for item in claims}
    if len(actual) != len(claims) or actual != expected:
        raise coverage.CoverageError(f"{path}: static-analysis archives do not match publication archives")
    return path


def _evidence_target(root, project_name, run_id, architecture, postgresql_version):
    target = Path(root) / "support/evidence" / (
        f"linux-publication-{run_id}" if project_name == "core"
        else f"postgis-publication-{run_id}")
    if project_name == "core" and postgresql_version != DEFAULT_PG_VERSION:
        target /= f"postgresql-{postgresql_version}"
    return target / architecture


def _selected_postgresql_versions(root):
    root = Path(root)
    support = coverage.load_json(root / "support.json")
    snapshot = coverage.load_json(root / "support/postgresql-releases.json")
    return set(coverage.release_snapshot(snapshot, support))


def import_run(root, core_artifact, postgis_artifact, run_id, architecture,
               postgresql_version=DEFAULT_PG_VERSION):
    """Validate and retain records, receipts, and compact evidence for a run."""
    root, core_artifact = Path(root), Path(core_artifact)
    postgis_artifact = Path(postgis_artifact) if postgis_artifact is not None else None
    run_id = str(run_id)
    if not re.fullmatch(r"\d+", run_id):
        raise coverage.CoverageError("run_id must contain digits only")
    if architecture not in ARCHITECTURES:
        raise coverage.CoverageError("architecture must be x86_64 or arm64")
    selected_versions = _selected_postgresql_versions(root)
    if postgresql_version not in selected_versions:
        raise coverage.CoverageError(
            f"postgresql_version {postgresql_version!r} is not selected; choose one of "
            f"{', '.join(sorted(selected_versions))}")
    platform = f"linux-{architecture}"
    support = coverage.load_json(root / "support.json")
    release_data = coverage.load_json(root / "support/postgresql-releases.json")
    releases = coverage.release_snapshot(release_data, support)
    vector_version = _selected_extension_version(
        support, releases, "pgvector", postgresql_version, platform)
    postgis_version = _selected_extension_version(
        support, releases, "PostGIS", postgresql_version, platform)
    core_dir = core_artifact / "pilot"
    core_publication = core_dir / "publication"
    postgis_dir = postgis_artifact / "postgis" if postgis_artifact is not None else None
    postgis_publication = (postgis_artifact / "postgis-publication"
                           if postgis_artifact is not None else None)
    core_records_dir = core_publication / "records"
    postgis_records_dir = postgis_publication / "records" if postgis_publication else None
    core_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    vector_name = f"pgvector-{vector_version}-postgresql-{postgresql_version}-{platform}.tar.gz"
    postgis_name = f"postgis-{postgis_version}-postgresql-{postgresql_version}-{platform}.tar.gz"
    paths = {"core": core_dir / core_name, "vector": core_dir / vector_name}
    if postgis_dir is not None:
        paths["postgis"] = postgis_dir / postgis_name
    digests = {}
    for name, path in paths.items():
        if path.is_file():
            digests[path.name] = _sha256(path)
            _sidecar(path, digests[path.name])

    profiles = {}
    steps_by_project = {"core": {}}
    receipts = {"core": {}}
    projects = [("core", core_publication)]
    if postgis_publication is not None:
        steps_by_project["postgis"] = {}
        receipts["postgis"] = {}
        projects.append(("postgis", postgis_publication))
    for project_name, publication_dir in projects:
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
                postgresql_version, vector_version, postgis_version,
                core_name if project_name == "postgis" else None)

    has_records = (_record_files(core_records_dir, run_id)
                   or (postgis_records_dir is not None and _record_files(postgis_records_dir, run_id)))
    has_receipts = any(receipt is not None for group in receipts.values()
                       for receipt in group.values())
    if not all(path.is_file() for path in paths.values()) and not has_records and not has_receipts:
        retained = []
        for project_name, publication_dir in projects:
            target = _evidence_target(root, project_name, run_id, architecture,
                                      postgresql_version)
            for endpoint in ("current",):
                source = publication_dir / f"{endpoint}-steps.json"
                _retain(source, target / source.name)
                retained.append(str((target / source.name).relative_to(root)))
        return retained

    support = coverage.load_json(root / "support.json")
    records = {"core": {}, "postgis": {}}
    record_dirs = [("core", core_records_dir)]
    if postgis_records_dir is not None:
        record_dirs.append(("postgis", postgis_records_dir))
    for project_name, directory in record_dirs:
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
                                      receipts[project_name][endpoint], postgresql_version,
                                      vector_version, postgis_version)
            receipt = receipts[project_name][endpoint]
            if record.get("test_revision") != receipt.get("test_revision"):
                raise coverage.CoverageError(f"{path}: record test revision differs from receipt")
            records[project_name].setdefault(endpoint, []).append((path, record))

    # Existing receipts imply that both archives named by the receipt were emitted.
    expected_project_archives = [("core", [core_name, vector_name])]
    if postgis_artifact is not None:
        expected_project_archives.append(("postgis", [postgis_name, core_name]))
    for project_name, names in expected_project_archives:
        for endpoint, receipt in receipts[project_name].items():
            if receipt is not None and any(name not in digests for name in names):
                raise coverage.CoverageError(f"{project_name} {endpoint} receipt exists but a referenced archive is missing")

    for project_name, _ in projects:
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

    analysis = {}
    analysis_specs = [("core", "static-analysis/core-pgvector.json", [core_name, vector_name])]
    if postgis_artifact is not None:
        analysis_specs.append(("postgis", "static-analysis/postgis.json", [core_name, postgis_name]))
    for project_name, relative, names in analysis_specs:
        receipt = receipts[project_name]["current"]
        passed = ((receipt is not None and all(value == "passed" for value in receipt["case_results"].values()))
                  or any(record.get("outcome") == "passed"
                         for _, record in records[project_name].get("current", [])))
        report_path = (core_publication if project_name == "core" else postgis_dir) / relative
        analysis[project_name] = _static_analysis(
            report_path, architecture,
            {name: digests[name] for name in names if name in digests}, passed)

    retained = []
    targets = {project_name: _evidence_target(root, project_name, run_id, architecture,
                                              postgresql_version)
               for project_name, _ in projects}
    for project_name, publication_dir in projects:
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
        report = analysis[project_name]
        if report is not None:
            destination = target / "static-analysis" / report.name
            _retain(report, destination)
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
    parser.add_argument("--postgis-artifact", type=Path,
                        help="extracted postgis-publication evidence artifact root")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    parser.add_argument("--postgresql-version", default=DEFAULT_PG_VERSION,
                        help="selected exact PostgreSQL version (defaults to the current 18.6 pilot)")
    args = parser.parse_args()
    try:
        paths = import_run(args.root, args.core_artifact, args.postgis_artifact,
                           args.run_id, args.architecture, args.postgresql_version)
        print("\n".join(paths))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
