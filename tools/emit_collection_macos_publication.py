#!/usr/bin/env python3
"""Bind collection macOS arm64 builds and checks to archive-specific records."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile

import coverage


PROFILE_ID = "collection-publication-macos-arm64-18.6"
PG_VERSION = "18.6"
ARCHITECTURE = "arm64"
PLATFORM = "macos-arm64"
CORE_NAME = f"postgresql-{PG_VERSION}-{PLATFORM}.tar.gz"
CORE_SHA256 = "bc543b0d54a8a33b3b737eab74d7f185035f01e5c2db4eb48be049996eee4440"
VERSIONS = {
    "1.1.1": "ab99a969334442e4a3c77405bc9ffed0083595d18f3898d64a731353a32bec5e",
    "2.1.3": "a6b07864e5893d3b682bb3223fd6d33015709765c9d40d415c85112358f0e3e4",
}
CASES = {"archive-suite", "static-analysis"}
ALLOWED_STEPS = {"success", "failure", "skipped", "cancelled", "timed_out"}


def _fail(message):
    raise coverage.CoverageError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sidecar(path, digest):
    sidecar = Path(path).with_name(Path(path).name + ".sha256")
    try:
        lines = sidecar.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fail(f"missing checksum sidecar for {Path(path).name}: {exc}")
    if (len(lines) != 1 or not re.fullmatch(rf"[0-9a-f]{{64}}  {re.escape(Path(path).name)}", lines[0])
            or lines[0].split()[0] != digest):
        _fail(f"checksum sidecar does not match {Path(path).name}")


def _metadata(path, version):
    source_url = f"https://github.com/aws/pgcollection/archive/refs/tags/v{version}.tar.gz"
    try:
        with tarfile.open(path, "r:gz") as archive:
            member = next((item for item in archive.getmembers()
                           if item.name == "metadata.json" and item.isfile()
                           and item.size <= 1024 * 1024), None)
            if member is None:
                _fail("collection archive requires bounded metadata.json")
            value = json.loads(archive.extractfile(member).read().decode("utf-8"))
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read collection archive metadata: {exc}")
    expected = {
        "project": "collection", "version": version, "sql_names": ["collection"],
        "requires": [], "configuration_prerequisites": [], "runtime_prerequisites": [],
        "postgresql_version": PG_VERSION, "platform": "macos", "architecture": ARCHITECTURE,
        "source": {"url": source_url, "sha256": VERSIONS[version]},
        "core_archive": {"basename": CORE_NAME, "sha256": CORE_SHA256},
    }
    if value != expected:
        _fail(f"collection {version} archive metadata differs from pinned identity")


def _report(path, digests):
    try:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"collection static analysis report is missing or invalid: {exc}")
    actual = report.get("archives") if isinstance(report, dict) else None
    if isinstance(actual, list):
        try:
            actual = {item["basename"]: item["sha256"] for item in actual}
        except (KeyError, TypeError):
            actual = None
    if (actual != digests or report.get("passed") is not True
            or report.get("architecture") != ARCHITECTURE
            or not any(item.get("file") == "lib/collection.dylib"
                       for item in report.get("inspected_files", []) if isinstance(item, dict))):
        _fail("collection Mach-O report does not pass against the final core and extension archives")


def emit(root, core_dir, archives, output, step_results, os_version, image_id, environ=None):
    root, core_dir, archives, output = map(Path, (root, core_dir, archives, output))
    environ = os.environ if environ is None else environ
    if not isinstance(step_results, dict) or set(step_results) != CASES or any(
            result not in ALLOWED_STEPS for result in step_results.values()):
        _fail("step_results must identify valid archive-suite and static-analysis outcomes")
    revision, run_id = environ.get("GITHUB_SHA", ""), environ.get("GITHUB_RUN_ID", "")
    if (not coverage.REVISION.fullmatch(revision) or not run_id.isdigit()
            or not environ.get("GITHUB_REPOSITORY") or not environ.get("GITHUB_SERVER_URL")):
        _fail("GitHub Actions revision and run provenance are required")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version or "") or not image_id:
        _fail("macOS runner version and image identifier are required")
    outcome_map = {"success": "passed", "failure": "failed", "timed_out": "failed",
                   "skipped": "skipped", "cancelled": "skipped"}
    results = {case: outcome_map[step_results[case]] for case in sorted(CASES)}
    publication_dir = output / "publication"
    publication_dir.mkdir(parents=True, exist_ok=True)
    attempt_path = publication_dir / "attempt.json"
    present = {CORE_NAME: (core_dir / CORE_NAME).is_file()}
    names = {version: f"collection-{version}-postgresql-{PG_VERSION}-{PLATFORM}.tar.gz"
             for version in VERSIONS}
    present.update({name: (archives / name).is_file() for name in names.values()})
    attempt = {"schema_version": 1, "run_id": run_id, "source_revision": revision,
               "profile_id": PROFILE_ID, "postgresql_version": PG_VERSION,
               "collection_versions": list(VERSIONS), "source_sha256": VERSIONS,
               "architecture": ARCHITECTURE, "steps": step_results,
               "archives_present": present,
               "release_eligibility": "blocked-pending-dependency-review"}
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    profile = coverage.verification_profile(root, PROFILE_ID)
    if (profile["scope"] != "publication" or profile["platforms"] != [PLATFORM]
            or profile["case_ids"] != sorted(CASES) or not profile["sources_available"]):
        _fail("registered profile does not match this collection publication suite")
    if not all(present.values()):
        return [attempt_path]

    core = core_dir / CORE_NAME
    digests = {CORE_NAME: sha256(core)}
    _sidecar(core, digests[CORE_NAME])
    if digests[CORE_NAME] != CORE_SHA256:
        _fail("PostgreSQL core archive differs from the selected passed build")
    for version, name in names.items():
        path = archives / name
        digests[name] = sha256(path)
        _sidecar(path, digests[name])
        _metadata(path, version)
    attempt["archives"] = digests
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{environ['GITHUB_SERVER_URL'].rstrip('/')}/{environ['GITHUB_REPOSITORY']}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    outputs = [attempt_path]
    for version, name in names.items():
        report_path = archives / f"static-analysis-collection-{version}.json"
        report_hash = sha256(report_path) if report_path.is_file() else None
        if results["static-analysis"] == "passed":
            _report(report_path, {CORE_NAME: digests[CORE_NAME], name: digests[name]})
        receipt = {"schema_version": 1, "profile_id": PROFILE_ID,
                   "profile_revision": profile["profile_revision"], "test_revision": revision,
                   "project": "collection", "version": version,
                   "postgresql_version": PG_VERSION, "architecture": ARCHITECTURE,
                   "platform": PLATFORM, "endpoint": "current", "case_results": results,
                   "archives": {CORE_NAME: digests[CORE_NAME], name: digests[name]},
                   "extension_archive": name, "reports": ({"static_analysis": report_hash}
                                                               if report_hash else {}),
                   "clean_system": True,
                   "dependency_check_profile": "macho-system-dependencies-v1",
                   "dependency_checks_passed": results["static-analysis"] == "passed",
                   "environment": {"os": "macos", "os_version": os_version,
                                   "architecture": ARCHITECTURE, "image_id": image_id},
                   "release_eligibility": "blocked-pending-dependency-review", "ci": ci}
        receipt_path = publication_dir / f"current-receipt-{version}.json"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        record = {"schema_version": 2, "scope": "publication", "profile_id": PROFILE_ID,
                  "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
                  "case_results": results, "test_revision": revision, "ci": ci,
                  "outcome": ("failed" if "failed" in results.values() else
                              "skipped" if "skipped" in results.values() else "passed"),
                  "sha256": digests[name], "component": "collection", "project": "collection",
                  "version": version, "platform": PLATFORM, "postgresql_version": PG_VERSION,
                  "assembled_core": {"archive": CORE_NAME, "sha256": digests[CORE_NAME],
                                     "version": PG_VERSION},
                  "prerequisite_archives": [],
                  "environment": {"os": "macos", "os_version": os_version,
                                  "architecture": ARCHITECTURE, "clean_system": True,
                                  "endpoint": "current", "image_id": image_id,
                                  "dependency_check_profile": receipt["dependency_check_profile"],
                                  "dependency_checks_passed": receipt["dependency_checks_passed"]},
                  "release_eligibility": "blocked-pending-dependency-review"}
        coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
        record_dir = publication_dir / "records"
        record_dir.mkdir(parents=True, exist_ok=True)
        record_path = record_dir / f"collection-{version}-postgresql-{PG_VERSION}-{PLATFORM}-current-{run_id}.json"
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outputs.extend((receipt_path, report_path, record_path))
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--archive-suite-result", required=True)
    parser.add_argument("--static-analysis-result", required=True)
    args = parser.parse_args()
    try:
        result = emit(args.root, args.core_archives, args.archives, args.output,
                      {"archive-suite": args.archive_suite_result,
                       "static-analysis": args.static_analysis_result},
                      args.os_version, args.image_id)
        print("\n".join(map(str, result)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"collection macOS publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
