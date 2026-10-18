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

VERSION = "3.7.0"
PG_VERSION = "18.6"
SOURCE_COMMIT = "fa11ff53eb49b863d9ffff37f6afd5ff9299c581"
PCRE2_SHA256 = "b6c68fdf6f3ac31388b50aa89ff0fc49c00c987c16e7b5146491d12003f2c8ed"
CORE_RUN = "39081368117"
CORE_SHA256 = {
    "x86_64": "f89a7047812324b85c3b0bb29a3118fc55a492b17956f1fe0d74d1788d33d680",
    "arm64": "0eb9c0144fd0b1669c594ce1ebcf7abdf4e1ae3f8e29e59a92833e476001e42b",
}
CASES = ("archive-suite", "elf-closure")
BLOCK = "pending-human-review-of-upstream-only-source-and-runtime-load-path-policy"


def profile_id(architecture):
    if architecture not in CORE_SHA256:
        raise coverage.CoverageError("unsupported architecture")
    return f"address-standardizer-publication-linux-{architecture}-{PG_VERSION}"


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
         source_revision, run_id, repository, server_url, image_id, kernel_release):
    root, archives, core_archives, output = map(Path, (root, archives, core_archives, output))
    selected = profile_id(architecture)
    if not coverage.REVISION.fullmatch(source_revision or "") or not str(run_id).isdigit():
        raise coverage.CoverageError("full source revision and numeric workflow run ID are required")
    if not repository or not server_url or not image_id:
        raise coverage.CoverageError("GitHub and runner image provenance are required")
    match = re.fullmatch(r"(\d+(?:\.\d+)+)(?:[-+].*)?", kernel_release or "")
    if not match:
        raise coverage.CoverageError("Linux kernel release must start with a numeric dotted version")
    kernel = match.group(1)
    minimum = coverage.load_json(root / "support.json")["os_support"]["linux"]["minimum_version"]
    if coverage._os_version_parts(kernel, "Linux kernel release") < coverage._os_version_parts(minimum, "Linux minimum version"):
        raise coverage.CoverageError("Linux kernel is below the supported floor")

    archive_name = f"address-standardizer-{VERSION}-postgresql-{PG_VERSION}-linux-{architecture}.tar.gz"
    core_name = f"postgresql-{PG_VERSION}-linux-{architecture}.tar.gz"
    archive, core = archives / archive_name, core_archives / core_name
    static_path = archives / "static-analysis" / "address-standardizer.json"
    static_outcome = read_json(static_path).get("outcome") if static_path.is_file() else None
    if static_outcome not in {None, "passed", "failed"}:
        raise coverage.CoverageError("ELF report outcome must be passed or failed")
    _step(build_result)
    results = _case_results(verify_result, static_outcome)
    profile = coverage.verification_profile(root, selected)
    output.mkdir(parents=True, exist_ok=True)
    attempt_path = output / "attempt.json"
    attempt = {
        "schema_version": 1, "run_id": str(run_id), "source_revision": source_revision,
        "profile_id": selected, "postgresql_version": PG_VERSION, "version": VERSION,
        "architecture": architecture, "core_run_id": CORE_RUN,
        "steps": {case: ("success" if result == "passed" else "failure" if result == "failed" else "skipped")
                  for case, result in results.items()},
        "workflow_steps": {"build": build_result, "verify": verify_result},
        "release_eligible": False, "redistribution_status": BLOCK,
        "archives_present": {core_name: core.is_file(), archive_name: archive.is_file()},
        "reports": {"elf_closure": digest(static_path)} if static_path.is_file() else {},
    }
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not archive.is_file() or not core.is_file():
        return (attempt_path,)

    checksums = {archive_name: digest(archive), core_name: digest(core)}
    for path in (archive, core):
        _sidecar(path, checksums[path.name])
    attempt["archives"] = checksums
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if checksums[core_name] != CORE_SHA256[architecture]:
        raise coverage.CoverageError("core archive differs from the pinned current PostgreSQL 18.6 archive")
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
                    "pcre2_license": archives / "PCRE2-COPYING.txt"}
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
               "project": "Address Standardizer", "version": VERSION, "postgresql_version": PG_VERSION,
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
              "platform": f"linux-{architecture}", "postgresql_version": PG_VERSION,
              "assembled_core": {"archive": core_name, "sha256": checksums[core_name], "version": PG_VERSION},
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
    parser.add_argument("--architecture", choices=tuple(CORE_SHA256), required=True)
    parser.add_argument("--build-result", required=True)
    parser.add_argument("--verify-result", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--kernel-release", required=True)
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.archives, args.core_archives, args.output, args.architecture,
                         args.build_result, args.verify_result, os.environ.get("GITHUB_SHA", ""),
                         os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_REPOSITORY", ""),
                         os.environ.get("GITHUB_SERVER_URL", ""), args.image_id, args.kernel_release):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Address Standardizer Linux publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
