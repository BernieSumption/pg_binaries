#!/usr/bin/env python3
"""Create verifier input for a Linux PostgreSQL publication run."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import coverage
import emit_linux_publication_records


DEPENDENCY_PROFILE = "linux-runtime-v1"


def _read_steps(path, case_ids):
    try:
        steps = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"cannot read step results JSON: {exc}") from exc
    if not isinstance(steps, dict) or set(steps) != set(case_ids):
        raise coverage.CoverageError("step results must identify exactly every registered profile case")
    if any(value not in {"success", "failure", "skipped"} for value in steps.values()):
        raise coverage.CoverageError("step results must be success, failure, or skipped")
    return {case: {"success": "passed", "failure": "failed", "skipped": "skipped"}[steps[case]]
            for case in case_ids}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def create(root, archives_dir, receipt_path, profile_id, postgresql_version,
           architecture, endpoint, kernel_release, distribution,
           distribution_version, image_id, dependency_check_profile,
           dependency_check_result, clean_system, step_results_path,
           environ=None):
    root, archives_dir, receipt_path = Path(root), Path(archives_dir), Path(receipt_path)
    environ = os.environ if environ is None else environ
    if architecture not in {"x86_64", "arm64"}:
        raise coverage.CoverageError("architecture must be x86_64 or arm64")
    if endpoint != "current":
        raise coverage.CoverageError("Linux publication endpoint must be current")
    if dependency_check_profile != DEPENDENCY_PROFILE:
        raise coverage.CoverageError(f"dependency_check_profile must be {DEPENDENCY_PROFILE}")
    if dependency_check_result not in {"success", "failure"}:
        raise coverage.CoverageError("dependency check result must be success or failure")
    if not isinstance(clean_system, bool):
        raise coverage.CoverageError("clean_system must be boolean")
    revision = environ.get("GITHUB_SHA", "")
    run_id = environ.get("GITHUB_RUN_ID", "")
    repository = environ.get("GITHUB_REPOSITORY", "")
    server_url = environ.get("GITHUB_SERVER_URL", "")
    if (not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", revision)
            or not run_id.isdigit() or not repository or not server_url):
        raise coverage.CoverageError("GitHub Actions SHA, run ID, repository, and server URL are required")
    profile = coverage.verification_profile(root, profile_id)
    platform = f"linux-{architecture}"
    if profile["scope"] != "publication" or platform not in profile["platforms"]:
        raise coverage.CoverageError("registered profile is not a Linux publication profile for this architecture")
    results = _read_steps(step_results_path, profile["case_ids"])
    version = postgresql_version
    if not re.fullmatch(r"\d+\.\d+", version):
        raise coverage.CoverageError("postgresql_version must be major.minor")
    vector_version = emit_linux_publication_records.selected_pgvector_version(root, version, platform)
    names = (f"postgresql-{version}-{platform}.tar.gz",
             f"pgvector-{vector_version}-postgresql-{version}-{platform}.tar.gz")
    archive_hashes = {name: _sha256(archives_dir / name) for name in names}
    clean = clean_system
    dep_passed = dependency_check_result == "success"
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    if outcome == "passed" and (not clean or not dep_passed):
        raise coverage.CoverageError("passed cases require a clean system and successful dependency checks")
    receipt = {
        "profile_id": profile_id,
        "profile_revision": profile["profile_revision"],
        "test_revision": revision,
        "postgresql_version": version,
        "architecture": architecture,
        "os": "linux",
        "clean_system": clean,
        "endpoint": endpoint,
        "kernel_release": kernel_release,
        "distribution": distribution,
        "distribution_version": distribution_version,
        "image_id": image_id,
        "dependency_check_profile": dependency_check_profile,
        "dependency_checks_passed": dep_passed,
        "case_results": results,
        "archives": archive_hashes,
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
        emit_linux_publication_records.emit(root, archives_dir, candidate, Path(temporary) / "records")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    parser.add_argument("--endpoint", choices=("current",), required=True)
    parser.add_argument("--kernel-release", required=True)
    parser.add_argument("--distribution", required=True)
    parser.add_argument("--distribution-version", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--dependency-check-profile", required=True)
    parser.add_argument("--dependency-check-result", choices=("success", "failure"), required=True)
    parser.add_argument("--clean-system", choices=("true", "false"), required=True)
    parser.add_argument("--step-results", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = create(args.root, args.archives, args.receipt, args.profile_id,
                        args.postgresql_version, args.architecture, args.endpoint,
                        args.kernel_release, args.distribution, args.distribution_version,
                        args.image_id, args.dependency_check_profile,
                        args.dependency_check_result, args.clean_system == "true",
                        args.step_results)
        print(result)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux publication receipt: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
