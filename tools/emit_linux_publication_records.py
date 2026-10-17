#!/usr/bin/env python3
"""Emit Linux PostgreSQL and pgvector publication records from verifier JSON.

Receipt schema: profile_id, profile_revision, test_revision, postgresql_version,
architecture, endpoint (minimum/current), kernel_release, distribution,
distribution_version, image_id, dependency_check_profile, dependency_checks_passed,
case_results (case ID to passed/failed/skipped), archives (canonical filename
to sha256), and ci (GitHub Actions provider, run_id, run_url, source_revision,
build_revision, test_revision). Archives and matching <name>.sha256 sidecars
must be in --archives. A receipt is verifier input, not publication approval.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import coverage


MINIMUM_KERNEL = (5, 15)
DEPENDENCY_PROFILE = "linux-runtime-v1"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _fail(message):
    raise coverage.CoverageError(message)


def _kernel(value):
    match = re.match(r"^(\d+(?:\.\d+)+)(?:[-+].*)?$", value) if isinstance(value, str) else None
    if not match:
        _fail("receipt kernel_release must be a numeric dotted Linux release")
    return tuple(int(part) for part in match.group(1).split("."))


def _sidecar(path, archive_name, digest):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fail(f"cannot read {path.name}: {exc}")
    if len(lines) != 1:
        _fail(f"{path.name} must contain exactly one checksum")
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^\s]+)", lines[0])
    if not match or Path(match.group(2)).name != archive_name or match.group(1).lower() != digest:
        _fail(f"{path.name} does not match {archive_name}")


def emit(root, archives, receipt_path, output):
    root, archives, output = Path(root), Path(archives), Path(output)
    receipt = coverage.load_json(Path(receipt_path))
    if not isinstance(receipt, dict):
        _fail("receipt must be a JSON object")
    required = ("profile_id", "profile_revision", "test_revision", "postgresql_version",
                "architecture", "os", "clean_system", "endpoint", "kernel_release", "distribution",
                "distribution_version", "image_id", "dependency_check_profile",
                "dependency_checks_passed", "case_results", "archives", "ci")
    missing = [key for key in required if key not in receipt]
    if missing:
        _fail(f"receipt is missing fields: {', '.join(missing)}")
    architecture = receipt["architecture"]
    if architecture not in {"x86_64", "arm64"}:
        _fail("architecture must be x86_64 or arm64")
    if receipt["os"] != "linux" or not isinstance(receipt["clean_system"], bool):
        _fail("receipt must identify Linux and declare clean_system as boolean")
    platform = f"linux-{architecture}"
    profile = coverage.verification_profile(root, receipt["profile_id"])
    if profile["scope"] != "publication" or platform not in profile["platforms"]:
        _fail("registered profile is not a publication profile for this platform")
    if not profile["sources_available"] or receipt["profile_revision"] not in profile["compatible_profile_revisions"]:
        _fail("receipt profile revision is stale")
    cases = profile["case_ids"]
    results = receipt["case_results"]
    if not isinstance(results, dict) or set(results) != set(cases):
        _fail("case_results must identify exactly every registered profile case")
    if any(value not in {"passed", "failed", "skipped"} for value in results.values()):
        _fail("case_results values must be passed, failed, or skipped")
    outcome = ("failed" if "failed" in results.values()
               else "skipped" if "skipped" in results.values()
               else "passed")
    revision = receipt["test_revision"]
    if not isinstance(revision, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", revision):
        _fail("test_revision must be a full Git commit hash")
    ci = receipt["ci"]
    if (not isinstance(ci, dict) or ci.get("provider") != "github-actions"
            or not isinstance(ci.get("run_id"), (str, int)) or not str(ci.get("run_id")).isdigit()
            or not isinstance(ci.get("run_url"), str)
            or not ci["run_url"].endswith(f"/actions/runs/{ci['run_id']}")
            or not ci["run_url"].startswith("https://github.com/")
            or any(not isinstance(ci.get(key), str) or ci[key].lower() != revision.lower()
                   for key in ("source_revision", "build_revision", "test_revision"))):
        _fail("receipt is missing matching GitHub Actions revision provenance")
    kernel = receipt["kernel_release"]
    kernel_parts = _kernel(kernel)
    endpoint = receipt["endpoint"]
    if endpoint == "minimum":
        if kernel_parts[:2] != MINIMUM_KERNEL:
            _fail("minimum endpoint must use Linux kernel 5.15")
    elif endpoint == "current":
        if kernel_parts[:2] <= MINIMUM_KERNEL:
            _fail("current endpoint kernel must be newer than 5.15")
    else:
        _fail("endpoint must be minimum or current")
    if (not isinstance(receipt["distribution"], str) or not receipt["distribution"]
            or not isinstance(receipt["distribution_version"], str)
            or not re.fullmatch(r"\d+(?:\.\d+)*", receipt["distribution_version"])):
        _fail("receipt must identify the Linux distribution and numeric version")
    if not isinstance(receipt["dependency_checks_passed"], bool):
        _fail("dependency_checks_passed must be boolean")
    if outcome == "passed" and (receipt["clean_system"] is not True
                                 or receipt["dependency_checks_passed"] is not True):
        _fail("passed records require a clean system and successful dependency checks")
    if (not isinstance(receipt["image_id"], str) or not receipt["image_id"]
            or receipt["dependency_check_profile"] != DEPENDENCY_PROFILE):
        _fail("receipt image or dependency-check profile is invalid")
    if outcome == "passed" and not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", receipt["image_id"]):
        _fail("passed records require image_id sha256:<64 hex digits>")
    version = receipt["postgresql_version"]
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+", version):
        _fail("postgresql_version must be major.minor")
    core_name = f"postgresql-{version}-{platform}.tar.gz"
    vector_name = f"pgvector-0.8.7-postgresql-{version}-{platform}.tar.gz"
    archive_receipt = receipt["archives"]
    if not isinstance(archive_receipt, dict) or set(archive_receipt) != {core_name, vector_name}:
        _fail("archives must identify exactly the canonical PostgreSQL and pgvector archives")
    digests = {}
    for name in (core_name, vector_name):
        claimed = archive_receipt[name]
        if not isinstance(claimed, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", claimed):
            _fail(f"receipt has malformed checksum for {name}")
        archive = archives / name
        digest = sha256_file(archive)
        if digest != claimed.lower():
            _fail(f"receipt checksum does not match {name}")
        _sidecar(archives / f"{name}.sha256", name, digest)
        digests[name] = digest
    support = coverage.load_json(root / "support.json")
    records = []
    for name, component, record_version in (
        (core_name, "postgresql", version), (vector_name, "vector", "0.8.7")):
        record = {
            "schema_version": 2,
            "scope": "publication",
            "profile_id": profile["profile_id"],
            "profile_revision": receipt["profile_revision"],
            "test_cases": cases,
            "case_results": results,
            "test_revision": revision,
            "ci": ci,
            "outcome": outcome,
            "sha256": digests[name],
            "component": component,
            "version": record_version,
            "platform": platform,
            "postgresql_version": version,
            "environment": {
                "os": "linux", "os_version": kernel, "kernel_release": kernel,
                "distribution": receipt["distribution"],
                "distribution_version": receipt["distribution_version"],
                "architecture": architecture, "clean_system": receipt["clean_system"],
                "endpoint": endpoint, "image_id": receipt["image_id"],
                "dependency_check_profile": receipt["dependency_check_profile"],
                "dependency_checks_passed": receipt["dependency_checks_passed"],
            },
        }
        if component != "postgresql":
            record["assembled_core"] = {"archive": core_name, "sha256": digests[core_name], "version": version}
        coverage.validate_verification_record(record, support, root)
        records.append(record)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for record, name in zip(records, (core_name, vector_name)):
        path = output / f"{name[:-7]}-{endpoint}-{ci['run_id']}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.archives, args.receipt, args.output):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux publication record: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
