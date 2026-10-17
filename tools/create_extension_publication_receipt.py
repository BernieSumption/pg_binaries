#!/usr/bin/env python3
"""Create a checksum-bound publication receipt for an assembled Linux extension."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import coverage
from create_linux_publication_receipt import _read_steps, _sha256
import emit_extension_publication_records


def create(root, archives, core_archives, receipt_path, profile_id, project,
           version, postgresql_version, archive_target, architecture, endpoint,
           kernel_release, distribution, distribution_version, image_id,
           dependency_check_result, clean_system, step_results_path,
           environ=None, prerequisite_archives=None):
    root, archives, core_archives, receipt_path = map(
        Path, (root, archives, core_archives, receipt_path))
    environ = os.environ if environ is None else environ
    if architecture not in {"x86_64", "arm64"}:
        raise coverage.CoverageError("architecture must be x86_64 or arm64")
    if endpoint != "current":
        raise coverage.CoverageError("Linux publication endpoint must be current")
    if dependency_check_result not in {"success", "failure"}:
        raise coverage.CoverageError("dependency check result must be success or failure")
    if not isinstance(clean_system, bool):
        raise coverage.CoverageError("clean_system must be boolean")
    revision = environ.get("GITHUB_SHA", "")
    run_id = environ.get("GITHUB_RUN_ID", "")
    repository = environ.get("GITHUB_REPOSITORY", "")
    server_url = environ.get("GITHUB_SERVER_URL", "")
    if (not coverage.REVISION.fullmatch(revision) or not run_id.isdigit()
            or not repository or not server_url):
        raise coverage.CoverageError("GitHub Actions SHA, run ID, repository, and server URL are required")
    profile = coverage.verification_profile(root, profile_id)
    platform = f"linux-{architecture}"
    if profile["scope"] != "publication" or platform not in profile["platforms"]:
        raise coverage.CoverageError("registered profile is not a Linux publication profile for this architecture")
    results = _read_steps(step_results_path, profile["case_ids"])
    if not re.fullmatch(r"\d+\.\d+", postgresql_version):
        raise coverage.CoverageError("postgresql_version must be major.minor")
    if not re.fullmatch(r"\d+\.\d+(?:-to-\d+\.\d+)?", archive_target):
        raise coverage.CoverageError("archive_target must be a PostgreSQL build or range")
    slug = coverage.archive_project_name(project)
    extension_name = (f"{slug}-{version}-postgresql-{archive_target}-"
                      f"{platform}.tar.gz")
    core_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    hashes = {extension_name: _sha256(archives / extension_name),
              core_name: _sha256(core_archives / core_name)}
    support = coverage.load_json(root / "support.json")
    selected = support.get("extensions", {}).get(project)
    if not isinstance(selected, dict):
        raise coverage.CoverageError("extension project is absent from declared support")
    required_projects = emit_extension_publication_records._metadata(
        archives / extension_name, slug, version, platform, archive_target,
        selected["sql_names"])
    if required_projects != selected.get("requires", []):
        raise coverage.CoverageError("extension archive prerequisites do not match declared support")
    supplied_prerequisites = prerequisite_archives or {}
    if set(supplied_prerequisites) != set(required_projects):
        raise coverage.CoverageError("prerequisite archives must identify exactly the required projects")
    prerequisite_records = []
    for prerequisite in required_projects:
        path = Path(supplied_prerequisites[prerequisite])
        reference = emit_extension_publication_records._prerequisite_archive(
            path, prerequisite, postgresql_version, platform, support)
        reference["sha256"] = _sha256(path)
        prerequisite_records.append(reference)
    dep_passed = dependency_check_result == "success"
    outcome = ("failed" if "failed" in results.values()
               else "skipped" if "skipped" in results.values() else "passed")
    if outcome == "passed" and (not clean_system or not dep_passed):
        raise coverage.CoverageError(
            "passed cases require a clean system and successful dependency checks")
    receipt = {
        "profile_id": profile_id,
        "profile_revision": profile["profile_revision"],
        "test_revision": revision,
        "project": project,
        "version": version,
        "postgresql_version": postgresql_version,
        "architecture": architecture,
        "endpoint": endpoint,
        "kernel_release": kernel_release,
        "distribution": distribution,
        "distribution_version": distribution_version,
        "image_id": image_id,
        "clean_system": clean_system,
        "dependency_check_profile": f"{slug}-runtime-v1",
        "dependency_checks_passed": dep_passed,
        "case_results": results,
        "extension_archive": extension_name,
        "archives": hashes,
        "prerequisite_archives": prerequisite_records,
        "ci": {
            "provider": "github-actions",
            "run_id": run_id,
            "run_url": f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}",
            "source_revision": revision,
            "build_revision": revision,
            "test_revision": revision,
        },
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        candidate = Path(temporary) / "receipt.json"
        candidate.write_text(json.dumps(receipt), encoding="utf-8")
        emit_extension_publication_records.emit(
            root, archives, core_archives, candidate, Path(temporary) / "records",
            supplied_prerequisites)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    return receipt_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--archive-target")
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    parser.add_argument("--endpoint", choices=("current",), required=True)
    parser.add_argument("--kernel-release", required=True)
    parser.add_argument("--distribution", required=True)
    parser.add_argument("--distribution-version", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--dependency-check-result", choices=("success", "failure"), required=True)
    parser.add_argument("--clean-system", choices=("true", "false"), required=True)
    parser.add_argument("--step-results", type=Path, required=True)
    parser.add_argument("--prerequisite-archive", action="append", default=[], metavar="PROJECT=PATH",
                        help="checksum-bind one required extension project archive")
    args = parser.parse_args()
    try:
        prerequisites = {}
        for value in args.prerequisite_archive:
            project, separator, path = value.partition("=")
            if not separator or not project or not path or project in prerequisites:
                raise coverage.CoverageError("prerequisite archive must be unique PROJECT=PATH")
            prerequisites[project] = Path(path)
        print(create(args.root, args.archives, args.core_archives, args.receipt,
                     args.profile_id, args.project, args.version, args.postgresql_version,
                     args.archive_target or args.postgresql_version, args.architecture,
                     args.endpoint, args.kernel_release, args.distribution,
                     args.distribution_version, args.image_id, args.dependency_check_result,
                     args.clean_system == "true", args.step_results,
                     prerequisite_archives=prerequisites))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"extension publication receipt: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
