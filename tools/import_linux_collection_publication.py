#!/usr/bin/env python3
"""Validate and retain collection Linux publication evidence."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import tarfile

import coverage
import linux_core_resolution
from import_linux_publication_run import _case_results, _outcome, _sha256, _static_analysis, _steps
from import_linux_tiger_publication import _sidecar


ARCHITECTURES = {"x86_64", "arm64"}
VERSIONS = ("1.1.1", "2.1.3")
SOURCE_SHA256 = {
    "1.1.1": "ab99a969334442e4a3c77405bc9ffed0083595d18f3898d64a731353a32bec5e",
    "2.1.3": "a6b07864e5893d3b682bb3223fd6d33015709765c9d40d415c85112358f0e3e4",
}
STEP_NAMES = {"core_build", "collection_build", "collection_verify"}
MAX_EVIDENCE_BYTES = 1024 * 1024


def _metadata(path, version, architecture, postgresql_version):
    try:
        with tarfile.open(path, "r:gz") as archive:
            member = next((item for item in archive.getmembers()
                           if item.name == "metadata.json" and item.isfile()
                           and item.size <= MAX_EVIDENCE_BYTES), None)
            if member is None:
                raise coverage.CoverageError("collection archive requires bounded metadata.json")
            metadata = json.loads(archive.extractfile(member).read().decode("utf-8"))
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"cannot read collection archive metadata: {exc}") from exc
    source = metadata.get("source") if isinstance(metadata, dict) else None
    expected_url = f"https://github.com/aws/pgcollection/archive/refs/tags/v{version}.tar.gz"
    if (not isinstance(metadata, dict) or metadata.get("project") != "collection"
            or metadata.get("version") != version or metadata.get("sql_names") != ["collection"]
            or metadata.get("requires") != [] or metadata.get("postgresql_version") != postgresql_version
            or metadata.get("platform") != "linux" or metadata.get("architecture") != architecture
            or source != {"url": expected_url, "sha256": SOURCE_SHA256[version]}):
        raise coverage.CoverageError("collection archive metadata or pinned source identity is invalid")


def _import_selected_run(root, core_artifact, collection_artifact, run_id, architecture,
                         postgresql_version, selected_version):
    root, core_artifact, collection_artifact = map(Path, (root, core_artifact, collection_artifact))
    postgresql_version, selected_version = str(postgresql_version), str(selected_version)
    if (not re.fullmatch(r"[1-9][0-9]*", str(run_id)) or architecture not in ARCHITECTURES
            or not re.fullmatch(r"\d+\.\d+", postgresql_version)
            or selected_version not in VERSIONS):
        raise coverage.CoverageError("expected numeric run_id and a selected Collection Linux target")
    support = coverage.load_json(root / "support.json")
    releases = coverage.release_snapshot(coverage.load_json(root / "support/postgresql-releases.json"), support)
    if postgresql_version not in releases:
        raise coverage.CoverageError(f"PostgreSQL {postgresql_version} is not selected")
    project = support.get("extensions", {}).get("collection")
    version_config = project.get("versions", {}).get(selected_version) if isinstance(project, dict) else None
    major = int(postgresql_version.split(".", 1)[0])
    if (not isinstance(version_config, dict)
            or major < version_config.get("postgresql_minimum_major", 0)
            or major > version_config.get("postgresql_maximum_major", major)):
        raise coverage.CoverageError(f"Collection {selected_version} does not support PostgreSQL {major}")
    _, targets = coverage.expected_targets(support, releases)
    platform = f"linux-{architecture}"
    if not any(sql == "collection" and version == selected_version and pg == postgresql_version
               and target_platform == platform for sql, version, pg, target_platform in targets):
        raise coverage.CoverageError("selected Collection version is not an exact supported target")

    profile_id = f"collection-publication-linux-{architecture}-{postgresql_version}-{selected_version}"
    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or platform not in profile["platforms"]
            or profile["case_ids"] != ["collection-archive-suite"]):
        raise coverage.CoverageError("profile does not match the selected Collection Linux publication target")
    collection_dir = collection_artifact / "collection"
    if not collection_dir.is_dir():
        collection_dir = collection_artifact
    publication = collection_artifact / "collection-publication"
    steps_path, attempt_path = publication / "current-steps.json", publication / "attempt.json"
    steps = _steps(steps_path, profile)
    attempt = coverage.load_json(attempt_path)
    expected_source = {selected_version: SOURCE_SHA256[selected_version]}
    if (not isinstance(attempt, dict) or attempt.get("schema_version") != 1
            or str(attempt.get("run_id")) != str(run_id)
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))
            or attempt.get("architecture") != architecture
            or attempt.get("postgresql_version") != postgresql_version
            or attempt.get("collection_versions") != [selected_version]
            or attempt.get("source_sha256") != expected_source
            or not isinstance(attempt.get("steps"), dict) or set(attempt["steps"]) != STEP_NAMES
            or any(value not in {"success", "failure", "skipped"} for value in attempt["steps"].values())):
        raise coverage.CoverageError("selected attempt identity, source pin, or step outcomes are invalid")
    image = attempt.get("verifier_image_id")
    if image != "unknown" and not re.fullmatch(r"sha256:[0-9a-f]{64}", str(image)):
        raise coverage.CoverageError("verifier image identity is malformed")
    build, verify = attempt["steps"]["collection_build"], attempt["steps"]["collection_verify"]
    suite = ("failure" if "failure" in (build, verify) or
             (build == verify == "success" and image == "unknown") else
             "success" if build == verify == "success" else "skipped")
    if steps != {"collection-archive-suite": suite}:
        raise coverage.CoverageError("publication case outcome differs from raw attempt outcomes")

    core_dir = core_artifact / "pilot"
    if not core_dir.is_dir():
        core_dir = core_artifact
    core_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    extension_name = f"collection-{selected_version}-postgresql-{postgresql_version}-{platform}.tar.gz"
    core_archive, extension_archive = core_dir / core_name, collection_dir / extension_name
    receipt_path = publication / f"current-receipt-{selected_version}.json"
    records = sorted((publication / "records").glob("*.json"))
    if len(records) > 1 or (records and not receipt_path.is_file()):
        raise coverage.CoverageError("selected run must contain at most one receipt and one record")
    archives = {core_name: core_archive, extension_name: extension_archive}
    digests = {name: _sha256(path) for name, path in archives.items() if path.is_file()}
    bound = receipt_path.is_file() or bool(records)
    for name, path in archives.items():
        if name in digests and (bound or path.with_name(name + ".sha256").exists()):
            _sidecar(path, digests[name])
    if bound and set(digests) != set(archives):
        raise coverage.CoverageError("receipt or record exists but a referenced archive is missing")
    if extension_name in digests:
        _metadata(extension_archive, selected_version, architecture, postgresql_version)
    resolution = core_dir / "core-resolution.json"
    if core_archive.is_file():
        try:
            checked = linux_core_resolution.validate_resolution(resolution, core_archive,
                                                                postgresql_version, architecture)
        except (ValueError, OSError, TypeError) as exc:
            raise coverage.CoverageError(f"invalid exact PostgreSQL core provenance: {exc}") from exc
        if (checked.get("origin") == "built"
                and (checked["provenance"].get("run_id") != str(run_id)
                     or checked["provenance"].get("run_sha") != attempt["source_revision"])):
            raise coverage.CoverageError("built core provenance does not match this run and source revision")

    target = (root / "support/evidence" / f"collection-publication-{run_id}" / architecture
              / postgresql_version / selected_version)
    copies = [(steps_path, target / steps_path.name), (attempt_path, target / attempt_path.name)]
    receipt_data = {}
    if receipt_path.is_file():
        receipt = coverage.load_json(receipt_path)
        expected = {"profile_id": profile_id, "project": "collection", "version": selected_version,
                    "postgresql_version": postgresql_version, "architecture": architecture,
                    "endpoint": "current", "case_results": _case_results(steps),
                    "extension_archive": extension_name, "prerequisite_archives": [],
                    "archives": digests}
        ci, revision = receipt.get("ci", {}), receipt.get("test_revision")
        if (not isinstance(receipt, dict) or any(receipt.get(key) != value for key, value in expected.items())
                or receipt.get("profile_revision") not in profile["compatible_profile_revisions"]
                or not isinstance(ci, dict) or str(ci.get("run_id")) != str(run_id)
                or ci.get("provider") != "github-actions"
                or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")
                or revision != attempt["source_revision"]
                or any(ci.get(key) != revision for key in ("source_revision", "build_revision", "test_revision"))):
            raise coverage.CoverageError("selected receipt identity or archive hashes do not match attempt")
        if (receipt.get("distribution") != "Alpine Linux"
                or not re.fullmatch(r"3\.22(?:\.\d+)?", str(receipt.get("distribution_version")))
                or not receipt.get("kernel_release") or receipt.get("image_id") != image
                or receipt.get("dependency_check_profile") != "collection-runtime-v1"):
            raise coverage.CoverageError("receipt must identify matching Alpine 3.22 verifier and runtime check")
        if _outcome(receipt["case_results"]) == "passed" and not (
                receipt.get("clean_system") is True and receipt.get("dependency_checks_passed") is True):
            raise coverage.CoverageError("passed receipt requires clean runtime and dependency checks")
        receipt_data[selected_version] = receipt
        copies.append((receipt_path, target / receipt_path.name))
    if records:
        record = coverage.load_json(records[0])
        coverage.validate_verification_record(record, support, root)
        results = _case_results(steps)
        expected = {"profile_id": profile_id, "component": "collection", "project": "collection",
                    "version": selected_version, "postgresql_version": postgresql_version,
                    "platform": platform, "case_results": results, "outcome": _outcome(results),
                    "test_cases": profile["case_ids"], "ci": receipt["ci"],
                    "test_revision": receipt["test_revision"], "sha256": digests[extension_name],
                    "assembled_core": {"archive": core_name, "sha256": digests[core_name],
                                       "version": postgresql_version}, "prerequisite_archives": []}
        filename = f"collection-{selected_version}-postgresql-{postgresql_version}-{platform}-current-{run_id}.json"
        if (any(record.get(key) != value for key, value in expected.items()) or records[0].name != filename
                or record.get("profile_revision") != receipt.get("profile_revision")
                or any(record.get("environment", {}).get(key) != receipt.get(key) for key in (
                    "endpoint", "architecture", "kernel_release", "distribution", "distribution_version",
                    "image_id", "clean_system", "dependency_check_profile", "dependency_checks_passed"))):
            raise coverage.CoverageError("selected record identity or archive checksum differs from receipt")
        copies.append((records[0], root / "support/verification" / records[0].name))
    report_path = collection_dir / "static-analysis" / f"collection-{selected_version}.json"
    if receipt_data:
        report = _static_analysis(report_path, architecture, digests,
                                  _outcome(receipt["case_results"]) == "passed")
        if report is not None:
            copies.append((report, target / "static-analysis" / report.name))
    if bound:
        copies.append((resolution, target / resolution.name))
    for source, destination in copies:
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise coverage.CoverageError(f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {source}")
        if destination.exists() and (destination.is_symlink() or not destination.is_file()
                                     or destination.read_bytes() != source.read_bytes()):
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return [str(destination.relative_to(root)) for _, destination in copies]


def import_run(root, core_artifact, collection_artifact, run_id, architecture, postgresql_version="18.6",
               selected_version=None):
    if selected_version is not None:
        return _import_selected_run(root, core_artifact, collection_artifact, run_id,
                                    architecture, postgresql_version, selected_version)
    root, core_artifact, collection_artifact = map(Path, (root, core_artifact, collection_artifact))
    run_id = str(run_id)
    if not re.fullmatch(r"\d+", run_id) or architecture not in ARCHITECTURES:
        raise coverage.CoverageError("expected numeric run_id and x86_64 or arm64 architecture")
    support = coverage.load_json(root / "support.json")
    snapshot = coverage.load_json(root / "support/postgresql-releases.json")
    if postgresql_version not in coverage.release_snapshot(snapshot, support):
        raise coverage.CoverageError(f"PostgreSQL {postgresql_version} is not selected")
    platform = f"linux-{architecture}"
    profile_id = f"collection-publication-current-{architecture}"
    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or platform not in profile["platforms"]
            or profile["case_ids"] != ["collection-archive-suite"]):
        raise coverage.CoverageError("profile does not match the collection Linux publication target")

    collection_dir = collection_artifact / "collection"
    if not collection_dir.is_dir():
        collection_dir = collection_artifact
    publication = collection_artifact / "collection-publication"
    steps_path, attempt_path = publication / "current-steps.json", publication / "attempt.json"
    steps = _steps(steps_path, profile)
    attempt = coverage.load_json(attempt_path)
    if (not isinstance(attempt, dict) or attempt.get("schema_version") != 1
            or str(attempt.get("run_id")) != run_id
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))
            or attempt.get("architecture") != architecture
            or attempt.get("postgresql_version") != postgresql_version
            or attempt.get("collection_versions") != list(VERSIONS)
            or attempt.get("source_sha256") != SOURCE_SHA256
            or not isinstance(attempt.get("steps"), dict)
            or set(attempt["steps"]) != STEP_NAMES
            or any(value not in {"success", "failure", "skipped"} for value in attempt["steps"].values())):
        raise coverage.CoverageError("attempt identity, source pins, or step outcomes are invalid")
    image = attempt.get("verifier_image_id")
    if image != "unknown" and not re.fullmatch(r"sha256:[0-9a-f]{64}", str(image)):
        raise coverage.CoverageError("verifier image identity is malformed")
    build, verify = attempt["steps"]["collection_build"], attempt["steps"]["collection_verify"]
    suite = ("failure" if "failure" in (build, verify) or
             (build == verify == "success" and image == "unknown") else
             "success" if build == verify == "success" else "skipped")
    if steps != {"collection-archive-suite": suite}:
        raise coverage.CoverageError("publication case outcome differs from raw attempt outcomes")

    core_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    core_dir = core_artifact / "pilot"
    if not core_dir.is_dir():
        core_dir = core_artifact
    extension_names = {version: f"collection-{version}-postgresql-{postgresql_version}-{platform}.tar.gz"
                       for version in VERSIONS}
    receipt_paths = {version: publication / f"current-receipt-{version}.json" for version in VERSIONS}
    records = sorted((publication / "records").glob("*.json"))
    receipt_data = {version: coverage.load_json(path) for version, path in receipt_paths.items()
                    if path.is_file()}
    bound = bool(receipt_data) or bool(records)
    archive_paths = {core_name: core_dir / core_name}
    archive_paths.update({name: collection_dir / name for name in extension_names.values()})
    digests = {name: _sha256(path) for name, path in archive_paths.items() if path.is_file()}
    for name, digest in digests.items():
        if bound or archive_paths[name].with_name(name + ".sha256").exists():
            _sidecar(archive_paths[name], digest)
    if bound and set(digests) != set(archive_paths):
        raise coverage.CoverageError("receipt or records exist but referenced archives are missing")
    for version, name in extension_names.items():
        if name in digests:
            _metadata(archive_paths[name], version, architecture, postgresql_version)

    target = root / "support/evidence" / f"collection-publication-{run_id}" / architecture
    copies = [(steps_path, target / steps_path.name), (attempt_path, target / attempt_path.name)]
    for version, receipt in receipt_data.items():
        extension_name = extension_names[version]
        expected = {"profile_id": profile_id, "project": "collection", "version": version,
                    "postgresql_version": postgresql_version, "architecture": architecture,
                    "endpoint": "current", "case_results": _case_results(steps),
                    "extension_archive": extension_name, "prerequisite_archives": [],
                    "archives": {core_name: digests[core_name], extension_name: digests[extension_name]}}
        ci = receipt.get("ci", {})
        revision = receipt.get("test_revision")
        if (not isinstance(receipt, dict)
                or any(receipt.get(key) != value for key, value in expected.items())
                or receipt.get("profile_revision") not in profile["compatible_profile_revisions"]
                or not isinstance(ci, dict) or str(ci.get("run_id")) != run_id
                or ci.get("provider") != "github-actions"
                or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")
                or revision != attempt.get("source_revision")
                or any(ci.get(key) != revision for key in ("source_revision", "build_revision", "test_revision"))):
            raise coverage.CoverageError(f"collection {version} receipt identity or archive hashes do not match attempt")
        if (receipt.get("distribution") != "Alpine Linux"
                or not re.fullmatch(r"3\.22(?:\.\d+)?", str(receipt.get("distribution_version")))
                or not receipt.get("kernel_release") or receipt.get("image_id") != image
                or receipt.get("dependency_check_profile") != "collection-runtime-v1"):
            raise coverage.CoverageError("receipt must identify matching Alpine 3.22 verifier and runtime check")
        if _outcome(receipt["case_results"]) == "passed" and not (
                receipt.get("clean_system") is True and receipt.get("dependency_checks_passed") is True):
            raise coverage.CoverageError("passed receipt requires clean runtime and dependency checks")
        copies.append((receipt_paths[version], target / receipt_paths[version].name))
    if records and set(receipt_data) != set(VERSIONS):
        raise coverage.CoverageError("records require receipts for both collection releases")
    if len(records) != len(receipt_data):
        raise coverage.CoverageError("expected one record for each collection receipt")
    for source in records:
        record = coverage.load_json(source)
        coverage.validate_verification_record(record, support, root)
        version = record.get("version")
        if version not in receipt_data:
            raise coverage.CoverageError("record names an unexpected collection release")
        receipt = receipt_data[version]
        extension_name = extension_names[version]
        results = _case_results(steps)
        expected = {"profile_id": profile_id, "component": "collection", "project": "collection",
                    "version": version, "postgresql_version": postgresql_version,
                    "platform": platform, "case_results": results, "outcome": _outcome(results),
                    "test_cases": profile["case_ids"], "ci": receipt["ci"],
                    "test_revision": receipt["test_revision"], "sha256": digests[extension_name],
                    "assembled_core": {"archive": core_name, "sha256": digests[core_name],
                                       "version": postgresql_version}, "prerequisite_archives": []}
        expected_filename = f"collection-{version}-postgresql-{postgresql_version}-{platform}-current-{run_id}.json"
        if (any(record.get(key) != value for key, value in expected.items())
                or source.name != expected_filename
                or record.get("profile_revision") != receipt.get("profile_revision")
                or any(record.get("environment", {}).get(key) != receipt.get(key) for key in (
                    "endpoint", "architecture", "kernel_release", "distribution",
                    "distribution_version", "image_id", "clean_system",
                    "dependency_check_profile", "dependency_checks_passed"))):
            raise coverage.CoverageError("record identity or archive checksum differs from receipt")
        copies.append((source, root / "support/verification" / source.name))

    passed = len(receipt_data) == len(VERSIONS) and all(
        _outcome(item["case_results"]) == "passed" for item in receipt_data.values())
    for version, name in extension_names.items():
        path = collection_dir / "static-analysis" / f"collection-{version}.json"
        report = _static_analysis(path, architecture,
                                  {core_name: digests[core_name], name: digests[name]}, passed)
        if report is not None:
            copies.append((report, target / "static-analysis" / report.name))
    for source, destination in copies:
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise coverage.CoverageError(f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {source}")
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True)
    parser.add_argument("--collection-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    parser.add_argument("--postgresql-version", default="18.6")
    parser.add_argument("--selected-version", choices=VERSIONS,
                        help="import one target-specific Collection release instead of legacy both-version evidence")
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact, args.collection_artifact,
                                   args.run_id, args.architecture, args.postgresql_version,
                                   args.selected_version)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux collection publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
