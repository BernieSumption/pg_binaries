#!/usr/bin/env python3
"""Emit archive-bound candidate records for Address Standardizer on Linux."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import coverage
import extension_archive_plan
import linux_core_resolution

VERSION = "3.7.0"
DEFAULT_PG_VERSION = "18.6"
SOURCE_COMMIT = "fa11ff53eb49b863d9ffff37f6afd5ff9299c581"
PCRE2_SHA256 = "b6c68fdf6f3ac31388b50aa89ff0fc49c00c987c16e7b5146491d12003f2c8ed"
CASES = ("archive-suite", "elf-closure")
BLOCK = "pending-dependency-provenance-and-redistribution-review"


def profile_id(architecture, pg_version=DEFAULT_PG_VERSION):
    if architecture not in {"x86_64", "arm64"}:
        raise coverage.CoverageError("unsupported architecture")
    if not re.fullmatch(r"\d+\.\d+", str(pg_version)):
        raise coverage.CoverageError("PostgreSQL target must be an exact major.minor release")
    return f"address-standardizer-publication-linux-{architecture}-{pg_version}"


def validate_target(root, architecture, pg_version, extension_version):
    support = coverage.load_json(Path(root) / "support.json")
    releases = coverage.load_json(Path(root) / "support/postgresql-releases.json")
    try:
        extension_archive_plan.select_target(
            extension_archive_plan.plan(support, releases), "Address Standardizer",
            f"linux-{architecture}", pg_version, extension_version)
    except (coverage.CoverageError, ValueError) as exc:
        raise coverage.CoverageError(f"unsupported selected Address Standardizer target: {exc}") from exc
    return coverage.verification_profile(
        root, profile_id(architecture, pg_version))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"invalid or missing JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"expected a JSON object in {path}")
    return value


def _sidecar(path, expected):
    sidecar = Path(str(path) + ".sha256")
    try:
        lines = sidecar.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise coverage.CoverageError(f"missing checksum sidecar for {path.name}") from exc
    if len(lines) != 1 or not re.fullmatch(rf"{expected}\s+\*?{re.escape(path.name)}", lines[0]):
        raise coverage.CoverageError(f"checksum sidecar does not match {path.name}")


def _step(result):
    mapping = {"success": "passed", "failure": "failed", "skipped": "skipped",
               "cancelled": "skipped", "timed_out": "failed"}
    if result not in mapping:
        raise coverage.CoverageError("workflow result must be a GitHub Actions outcome")
    return mapping[result]


def _case_results(verify_result, elf_outcome):
    if verify_result not in {"success", "failure", "skipped", "cancelled", "timed_out"}:
        raise coverage.CoverageError("verify result must be a GitHub Actions outcome")
    elf = "passed" if elf_outcome == "passed" else "failed" if elf_outcome == "failed" else "skipped"
    archive = ("passed" if verify_result == "success" else
               "failed" if verify_result in {"failure", "timed_out"} and elf == "passed" else "skipped")
    return {"archive-suite": archive, "elf-closure": elf}


def emit(root, archives, core_archives, output, architecture, build_result, verify_result,
         source_revision, run_id, repository, server_url, image_id, kernel_release,
         pg_version=DEFAULT_PG_VERSION, core_resolution_path=None, core_resolution_result=None,
         extension_version=VERSION):
    root, archives, core_archives, output = map(Path, (root, archives, core_archives, output))
    selected = profile_id(architecture, pg_version)
    profile = validate_target(root, architecture, pg_version, extension_version)
    if not coverage.REVISION.fullmatch(source_revision or "") or not str(run_id).isdigit():
        raise coverage.CoverageError("full source revision and numeric workflow run ID are required")
    if not repository or not server_url:
        raise coverage.CoverageError("GitHub provenance is required")
    match = re.fullmatch(r"(\d+(?:\.\d+)+)(?:[-+].*)?", kernel_release or "")
    if not match:
        raise coverage.CoverageError("Linux kernel release must start with a numeric dotted version")
    kernel = match.group(1)
    minimum = coverage.load_json(root / "support.json")["os_support"]["linux"]["minimum_version"]
    if coverage._os_version_parts(kernel, "Linux kernel release") < coverage._os_version_parts(minimum, "Linux minimum version"):
        raise coverage.CoverageError("Linux kernel is below the supported floor")

    archive_name = f"address-standardizer-{extension_version}-postgresql-{pg_version}-linux-{architecture}.tar.gz"
    core_name = f"postgresql-{pg_version}-linux-{architecture}.tar.gz"
    archive, core = archives / archive_name, core_archives / core_name
    resolution_path = Path(core_resolution_path) if core_resolution_path else None
    resolution = None
    if core_resolution_result is None and resolution_path is not None and resolution_path.is_file():
        core_resolution_result = "success"
    if core_resolution_result not in {"success", "failure", "skipped", "cancelled", "timed_out"}:
        raise coverage.CoverageError("core resolution result must be a GitHub Actions outcome")
    if core_resolution_result == "success" and resolution_path is not None and resolution_path.is_file():
        try:
            resolution = linux_core_resolution.validate_resolution(
                resolution_path, core, pg_version, architecture)
        except (OSError, ValueError) as exc:
            raise coverage.CoverageError(f"invalid resolved PostgreSQL core provenance: {exc}") from exc
        core_run = str(resolution["provenance"]["run_id"])
    elif core_resolution_result == "success":
        raise coverage.CoverageError("successful core resolution is missing its provenance record")
    else:
        core_run = None
    static_path = archives / "static-analysis" / "address-standardizer.json"
    static_outcome = read_json(static_path).get("outcome") if static_path.is_file() else None
    if static_outcome not in {None, "passed", "failed"}:
        raise coverage.CoverageError("ELF report outcome must be passed or failed")
    _step(build_result)
    results = _case_results(verify_result, static_outcome)
    output.mkdir(parents=True, exist_ok=True)
    attempt_path = output / "attempt.json"
    workflow_steps = {"build": build_result, "verify": verify_result}
    workflow_steps["core_resolution"] = core_resolution_result
    attempt = {
        "schema_version": 1, "run_id": str(run_id), "source_revision": source_revision,
        "profile_id": selected, "postgresql_version": pg_version, "version": extension_version,
        "architecture": architecture, "core_run_id": core_run,
        "steps": {case: ("success" if result == "passed" else "failure" if result == "failed" else "skipped")
                  for case, result in results.items()},
        "workflow_steps": workflow_steps,
        "release_eligible": False, "redistribution_status": BLOCK,
        "archives_present": {core_name: core.is_file(), archive_name: archive.is_file()},
        "reports": {"elf_closure": digest(static_path)} if static_path.is_file() else {},
    }
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if resolution is None or extension_version != VERSION:
        return (attempt_path,)
    if not archive.is_file() or not core.is_file():
        return (attempt_path,)
    if not image_id or image_id == "unavailable":
        raise coverage.CoverageError("runner verifier image provenance is required for complete archives")

    checksums = {archive_name: digest(archive), core_name: digest(core)}
    for path in (archive, core):
        _sidecar(path, checksums[path.name])
    attempt["archives"] = checksums
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if static_path.is_file():
        static = read_json(static_path)
        if (static.get("architecture") != architecture or static.get("outcome") != static_outcome
                or static.get("archives") != [
                    {"basename": core_name, "sha256": checksums[core_name]},
                    {"basename": archive_name, "sha256": checksums[archive_name]},
                ]):
            raise coverage.CoverageError("ELF report is not bound to the final archive")
    build_evidence = archives / "build-evidence.txt"
    if (f"address_standardizer_source_commit={SOURCE_COMMIT}" not in build_evidence.read_text(encoding="utf-8")
            or f"pcre2_source_sha256={PCRE2_SHA256}" not in build_evidence.read_text(encoding="utf-8")):
        raise coverage.CoverageError("build evidence does not identify the pinned upstream sources")

    report_paths = {"elf_closure": static_path, "build_evidence": build_evidence,
                    "address_standardizer_license": archives / "Address-Standardizer-COPYING.txt",
                    "pcre2_license": archives / "PCRE2-LICENCE.md",
                    "sljit_license": archives / "SLJIT-LICENSE.txt"}
    if resolution is not None:
        report_paths["core_resolution"] = resolution_path
    for key, path in report_paths.items():
        if not path.is_file():
            raise coverage.CoverageError(f"candidate evidence is missing {path.name}")
        attempt["reports"][key] = digest(path)
    probe = archives / "probe-output.txt"
    if probe.is_file():
        attempt["reports"]["probe_output"] = digest(probe)
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ci = {"provider": "github-actions", "run_id": str(run_id),
          "run_url": f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}",
          "source_revision": source_revision, "build_revision": source_revision,
          "test_revision": source_revision}
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    environment = {"os": "linux", "os_version": kernel, "distribution": "Alpine Linux 3.22",
                   "architecture": architecture, "clean_system": True, "endpoint": "current",
                   "image_id": image_id, "dependency_check_profile": "linux-elf-alpine-relocation-v1",
                   "dependency_checks_passed": results["elf-closure"] == "passed"}
    receipt = {"schema_version": 1, "profile_id": selected,
               "profile_revision": profile["profile_revision"], "test_revision": source_revision,
               "project": "Address Standardizer", "version": VERSION, "postgresql_version": pg_version,
               "architecture": architecture, "platform": f"linux-{architecture}", "endpoint": "current",
               "case_results": results, "archives": checksums, "extension_archive": archive_name,
               "reports": {key: digest(path) for key, path in report_paths.items()},
               "clean_system": True, "dependency_check_profile": "linux-elf-alpine-relocation-v1",
               "dependency_checks_passed": results["elf-closure"] == "passed",
               "release_eligible": False, "redistribution_status": BLOCK,
               "environment": environment, "ci": ci}
    receipt_path = output / "current-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = {"schema_version": 2, "scope": "publication", "profile_id": selected,
              "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
              "case_results": results, "test_revision": source_revision, "ci": ci, "outcome": outcome,
              "sha256": checksums[archive_name], "component": "address_standardizer",
              "project": "Address Standardizer", "version": VERSION,
              "platform": f"linux-{architecture}", "postgresql_version": pg_version,
              "assembled_core": {"archive": core_name, "sha256": checksums[core_name], "version": pg_version},
              "prerequisite_archives": [], "release_eligible": False,
              "redistribution_status": BLOCK, "environment": environment}
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    record_path = output / "verification-record.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return attempt_path, receipt_path, record_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--extension-version", required=True)
    parser.add_argument("--build-result", required=True)
    parser.add_argument("--verify-result", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--kernel-release", required=True)
    parser.add_argument("--core-resolution", type=Path)
    parser.add_argument("--core-resolution-result", choices=("success", "failure", "skipped", "cancelled", "timed_out"))
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.archives, args.core_archives, args.output, args.architecture,
                         args.build_result, args.verify_result, os.environ.get("GITHUB_SHA", ""),
                         os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_REPOSITORY", ""),
                         os.environ.get("GITHUB_SERVER_URL", ""), args.image_id, args.kernel_release,
                         args.postgresql_version, args.core_resolution, args.core_resolution_result,
                         args.extension_version):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Address Standardizer Linux publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
