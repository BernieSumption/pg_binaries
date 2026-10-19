#!/usr/bin/env python3
"""Validate and retain one archive-bound collection macOS publication attempt."""

import argparse
import json
from pathlib import Path
import shutil
import sys

import coverage
import emit_collection_macos_publication as publication


MAX_EVIDENCE_BYTES = 1024 * 1024


def _read(path):
    value = coverage.load_json(path)
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"{path}: expected JSON object")
    return value


def _retain(source, destination, copies):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
        raise coverage.CoverageError(f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {source}")
    if destination.exists() and destination.read_bytes() != source.read_bytes():
        raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    copies.append((source, destination))


def _copy(copies):
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)


def import_run(root, core_artifact, collection_artifact, run_id, target_config=None):
    root, core_artifact, collection_artifact = map(Path, (root, core_artifact, collection_artifact))
    target = publication.selected_target(target_config)
    pg_version, architecture = target.postgresql_version, target.architecture
    platform, profile_id, core_name = target.platform, target.profile_id, target.core_basename
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run_id must be numeric")
    support = coverage.load_json(root / "support.json")
    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or profile["platforms"] != [platform]
            or profile["case_ids"] != sorted(publication.CASES)):
        raise coverage.CoverageError("registered profile does not match scoped collection target")

    publication_dir = collection_artifact / "publication"
    attempt_path = publication_dir / "attempt.json"
    attempt = _read(attempt_path)
    if (attempt.get("schema_version") != 1 or str(attempt.get("run_id")) != run_id
            or attempt.get("profile_id") != profile_id
            or attempt.get("architecture") != architecture
            or attempt.get("postgresql_version") != pg_version
            or attempt.get("collection_versions") != list(publication.VERSIONS)
            or attempt.get("source_sha256") != publication.VERSIONS
            or attempt.get("release_eligibility") != "blocked-pending-dependency-review"
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))):
        raise coverage.CoverageError("raw attempt identity or pinned source hashes are invalid")
    raw_steps = attempt.get("steps")
    if (not isinstance(raw_steps, dict) or set(raw_steps) != publication.CASES
            or any(value not in publication.ALLOWED_STEPS for value in raw_steps.values())):
        raise coverage.CoverageError("raw attempt must retain each publication case outcome")
    results = {case: {"success": "passed", "failure": "failed", "timed_out": "failed",
                      "skipped": "skipped", "cancelled": "skipped"}[raw_steps[case]]
               for case in sorted(publication.CASES)}
    evidence = root / "support/evidence" / f"collection-macos-publication-{run_id}" / architecture
    copies = []
    _retain(attempt_path, evidence / "attempt.json", copies)

    core = core_artifact / core_name
    extension_names = {version: target.extension_basename(version) for version in publication.VERSIONS}
    archives = {core_name: core}
    archives.update({name: collection_artifact / name for name in extension_names.values()})
    receipt_paths = {version: publication_dir / f"current-receipt-{version}.json"
                     for version in publication.VERSIONS}
    record_paths = sorted((publication_dir / "records").glob("*.json"))
    receipts_present = {version: path.is_file() for version, path in receipt_paths.items()}
    if not all(path.is_file() for path in archives.values()):
        if any(receipts_present.values()) or record_paths:
            raise coverage.CoverageError("receipt or record exists without every referenced final archive")
        for name in ("build-log.txt", "probe-1.1.1.txt", "probe-2.1.3.txt",
                     "integer-collection-probe.txt", "static-analysis-collection-1.1.1.json",
                     "static-analysis-collection-2.1.3.json"):
            path = collection_artifact / name
            if path.is_file():
                _retain(path, evidence / name, copies)
        _copy(copies)
        return [str(destination.relative_to(root)) for _, destination in copies]

    if (not any(receipts_present.values()) and not record_paths
            and any(value != "success" for value in raw_steps.values())):
        for version in publication.VERSIONS:
            for name in (f"static-analysis-collection-{version}.json", f"probe-{version}.txt"):
                path = collection_artifact / name
                if path.is_file():
                    _retain(path, evidence / name, copies)
        for name in ("build-log.txt", "integer-collection-probe.txt"):
            path = collection_artifact / name
            if path.is_file():
                _retain(path, evidence / name, copies)
        _copy(copies)
        return [str(destination.relative_to(root)) for _, destination in copies]

    digests = {name: publication.sha256(path) for name, path in archives.items()}
    publication._sidecar(core, digests[core_name])
    if digests[core_name] != target.core_sha256:
        raise coverage.CoverageError("core archive differs from resolved target")
    for version, name in extension_names.items():
        path = archives[name]
        publication._sidecar(path, digests[name])
        publication._metadata(path, version, target)
    if attempt.get("archives") != digests:
        raise coverage.CoverageError("raw attempt hashes differ from final archive bytes")

    if any(receipts_present.values()) and not all(receipts_present.values()):
        raise coverage.CoverageError("expected receipts for both collection releases")
    if record_paths and not all(receipts_present.values()):
        raise coverage.CoverageError("verification records require both matching receipts")
    expected_records = set()
    for version, name in extension_names.items():
        report_path = collection_artifact / f"static-analysis-collection-{version}.json"
        receipt_path = receipt_paths[version]
        if not receipt_path.is_file():
            continue
        receipt = _read(receipt_path)
        expected_archives = {core_name: digests[core_name], name: digests[name]}
        ci = receipt.get("ci")
        expected = {"schema_version": 1, "profile_id": profile_id,
                    "profile_revision": profile["profile_revision"],
                    "test_revision": attempt["source_revision"], "project": "collection",
                    "version": version, "postgresql_version": pg_version,
                    "architecture": architecture, "platform": platform,
                    "endpoint": "current", "case_results": results,
                    "archives": expected_archives, "extension_archive": name,
                    "release_eligibility": "blocked-pending-dependency-review"}
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise coverage.CoverageError(f"collection {version} receipt identity or hashes differ from final archives")
        if (receipt.get("clean_system") is not True
                or receipt.get("dependency_check_profile") != "macho-system-dependencies-v1"
                or receipt.get("dependency_checks_passed") != (results["static-analysis"] == "passed")
                or receipt.get("reports") != ({"static_analysis": publication.sha256(report_path)}
                                                 if report_path.is_file() else {})
                or not isinstance(receipt.get("environment"), dict)
                or receipt["environment"].get("os") != "macos"
                or receipt["environment"].get("architecture") != architecture
                or not receipt["environment"].get("image_id")):
            raise coverage.CoverageError(f"collection {version} receipt environment or report hashes are invalid")
        if (not isinstance(ci, dict) or ci.get("provider") != "github-actions"
                or str(ci.get("run_id")) != run_id
                or any(ci.get(key) != attempt["source_revision"]
                       for key in ("source_revision", "build_revision", "test_revision"))
                or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")):
            raise coverage.CoverageError("receipt CI provenance differs from raw attempt")
        if results["static-analysis"] == "passed":
            publication._report(report_path, expected_archives,
                                 publication._module_path(archives[extension_names[version]]), target)
        _retain(receipt_path, evidence / receipt_path.name, copies)
        expected_records.add(f"collection-{version}-postgresql-{pg_version}-{platform}-current-{run_id}.json")

    if record_paths and {path.name for path in record_paths} != expected_records:
        raise coverage.CoverageError("expected exactly one verification record per collection receipt")
    if receipts_present["1.1.1"] and not record_paths:
        raise coverage.CoverageError("receipts exist without verification records")
    for source in record_paths:
        record = _read(source)
        coverage.validate_verification_record(record, support, root)
        version = record.get("version")
        if version not in extension_names:
            raise coverage.CoverageError("record names an unexpected collection release")
        name = extension_names[version]
        receipt = _read(receipt_paths[version])
        expected = {"profile_id": profile_id, "component": "collection",
                    "project": "collection", "version": version,
                    "postgresql_version": pg_version, "platform": platform,
                    "case_results": results,
                    "outcome": ("failed" if "failed" in results.values() else
                                "skipped" if "skipped" in results.values() else "passed"),
                    "test_cases": profile["case_ids"], "ci": receipt["ci"],
                    "test_revision": attempt["source_revision"], "sha256": digests[name],
                    "assembled_core": {"archive": core_name,
                                       "sha256": digests[core_name],
                                       "version": pg_version},
                    "prerequisite_archives": [],
                    "release_eligibility": "blocked-pending-dependency-review"}
        if (any(record.get(key) != value for key, value in expected.items())
                or source.name not in expected_records
                or any(record.get("environment", {}).get(key) != receipt.get("environment", {}).get(key)
                       for key in ("os", "os_version", "architecture", "image_id"))
                or record.get("environment", {}).get("dependency_checks_passed") != receipt.get("dependency_checks_passed")):
            raise coverage.CoverageError("record identity or final archive checksum differs from receipt")
        _retain(source, root / "support/verification" / source.name, copies)

    for version in publication.VERSIONS:
        for name in (f"static-analysis-collection-{version}.json", f"probe-{version}.txt"):
            path = collection_artifact / name
            if path.is_file():
                _retain(path, evidence / name, copies)
    for name in ("build-log.txt", "integer-collection-probe.txt"):
        path = collection_artifact / name
        if path.is_file():
            _retain(path, evidence / name, copies)
    _copy(copies)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--target-config", type=Path)
    parser.add_argument("--core-artifact", type=Path, required=True)
    parser.add_argument("--collection-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact,
                                   args.collection_artifact, args.run_id, args.target_config)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"collection macOS publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
