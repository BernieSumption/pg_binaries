#!/usr/bin/env python3
"""Emit checksum-bound Linux publication records for one extension project."""

import argparse
import json
from pathlib import Path
import re
import sys
import tarfile

import coverage
from emit_linux_publication_records import _kernel, _sidecar, sha256_file


def _fail(message):
    raise coverage.CoverageError(message)


def _metadata(path, project_name, version, platform, archive_target, sql_names):
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = {member.name: member for member in archive.getmembers()}
            member = members.get("metadata.json")
            if member is None or not member.isfile() or member.size > 1024 * 1024:
                _fail("extension archive requires a regular metadata.json")
            metadata = json.loads(archive.extractfile(member).read().decode("utf-8"))
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read extension archive metadata: {exc}")
    os_name, architecture = platform.split("-", 1)
    if (not isinstance(metadata, dict) or metadata.get("project") != project_name
            or metadata.get("version") != version or metadata.get("platform") != os_name
            or metadata.get("architecture") != architecture
            or metadata.get("sql_names") != sql_names):
        _fail("extension archive metadata does not match declared target")
    build_version = metadata.get("postgresql_version")
    if not isinstance(build_version, str) or not re.fullmatch(r"\d+\.\d+", build_version):
        _fail("extension archive metadata requires a PostgreSQL build version")
    if "-to-" in archive_target:
        low, high = archive_target.split("-to-", 1)
        if not (coverage.version_parts(low, "archive range")
                <= coverage.version_parts(build_version, "archive build version")
                <= coverage.version_parts(high, "archive range")):
            _fail("extension archive build version is outside its filename range")
    elif build_version != archive_target:
        _fail("extension archive build version does not match its filename")


def emit(root, archives, core_archives, receipt_path, output):
    root, archives, core_archives, output = map(Path, (root, archives, core_archives, output))
    receipt = coverage.load_json(Path(receipt_path))
    if not isinstance(receipt, dict):
        _fail("receipt must be a JSON object")
    required = ("profile_id", "profile_revision", "test_revision", "project", "version",
                "postgresql_version", "architecture", "endpoint", "kernel_release",
                "distribution", "distribution_version", "image_id", "clean_system",
                "dependency_check_profile", "dependency_checks_passed", "case_results",
                "extension_archive", "archives", "ci")
    missing = [key for key in required if key not in receipt]
    if missing:
        _fail(f"receipt is missing fields: {', '.join(missing)}")
    architecture = receipt["architecture"]
    if architecture not in {"x86_64", "arm64"}:
        _fail("architecture must be x86_64 or arm64")
    platform = f"linux-{architecture}"
    profile = coverage.verification_profile(root, receipt["profile_id"])
    if profile["scope"] != "publication" or platform not in profile["platforms"]:
        _fail("registered profile is not a Linux publication profile for this architecture")
    if (not profile["sources_available"]
            or receipt["profile_revision"] not in profile["compatible_profile_revisions"]):
        _fail("receipt profile revision is stale")
    results = receipt["case_results"]
    if (not isinstance(results, dict) or set(results) != set(profile["case_ids"])
            or any(value not in {"passed", "failed", "skipped"} for value in results.values())):
        _fail("case_results must cover exactly the registered cases")
    outcome = ("failed" if "failed" in results.values()
               else "skipped" if "skipped" in results.values() else "passed")
    revision = receipt["test_revision"]
    if not isinstance(revision, str) or not coverage.REVISION.fullmatch(revision):
        _fail("test_revision must be a full Git commit hash")
    ci = receipt["ci"]
    if (not isinstance(ci, dict) or ci.get("provider") != "github-actions"
            or not str(ci.get("run_id", "")).isdigit()
            or not isinstance(ci.get("run_url"), str)
            or not ci["run_url"].startswith("https://github.com/")
            or not ci["run_url"].endswith(f"/actions/runs/{ci['run_id']}")
            or ci.get("source_revision") != revision or ci.get("test_revision") != revision
            or ci.get("build_revision") != revision):
        _fail("receipt is missing GitHub Actions revision provenance")
    kernel = receipt["kernel_release"]
    parts = _kernel(kernel)
    endpoint = receipt["endpoint"]
    if endpoint == "minimum":
        if parts[:2] != (5, 15):
            _fail("minimum endpoint must use Linux kernel 5.15")
    elif endpoint == "current":
        if parts[:2] <= (5, 15):
            _fail("current endpoint kernel must be newer than 5.15")
    else:
        _fail("endpoint must be minimum or current")
    if (not isinstance(receipt["distribution"], str) or not receipt["distribution"]
            or not isinstance(receipt["distribution_version"], str)
            or not re.fullmatch(r"\d+(?:\.\d+)*", receipt["distribution_version"])):
        _fail("receipt must identify a Linux distribution and numeric version")
    if (not isinstance(receipt["clean_system"], bool)
            or not isinstance(receipt["dependency_checks_passed"], bool)
            or not isinstance(receipt["image_id"], str) or not receipt["image_id"]
            or not isinstance(receipt["dependency_check_profile"], str)
            or not receipt["dependency_check_profile"]):
        _fail("receipt environment declarations are incomplete")
    if outcome == "passed" and (not receipt["clean_system"]
                                or not receipt["dependency_checks_passed"]
                                or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", receipt["image_id"])):
        _fail("passed records require a clean environment, dependency checks and image digest")
    support = coverage.load_json(root / "support.json")
    coverage.validate_support(support)
    project = receipt["project"]
    if project not in support["extensions"]:
        _fail("extension project is absent from declared support")
    selected = support["extensions"][project]
    version = receipt["version"]
    if version not in selected["versions"]:
        _fail("extension version is absent from declared support")
    pg_version = receipt["postgresql_version"]
    if not isinstance(pg_version, str) or not re.fullmatch(r"\d+\.\d+", pg_version):
        _fail("postgresql_version must be major.minor")
    releases = coverage.release_snapshot(
        coverage.load_json(root / "support/postgresql-releases.json"), support)
    _, intended = coverage.expected_targets(support, releases)
    if any((name, version, pg_version, platform) not in intended
           for name in selected["sql_names"]):
        _fail("extension target is absent from declared support")
    project_name = coverage.archive_project_name(project)
    if receipt["dependency_check_profile"] != f"{project_name}-runtime-v1":
        _fail("dependency check profile does not match the extension project")
    extension_name = receipt["extension_archive"]
    if not isinstance(extension_name, str):
        _fail("extension_archive must be a filename")
    match = re.fullmatch(
        rf"{re.escape(project_name)}-{re.escape(version)}-postgresql-"
        rf"(\d+\.\d+(?:-to-\d+\.\d+)?)-{re.escape(platform)}\.tar\.gz",
        extension_name)
    if not match:
        _fail("extension_archive must be a canonical filename for this target")
    if "-to-" in match.group(1):
        low, high = match.group(1).split("-to-", 1)
        if not (coverage.version_parts(low, "archive range")
                <= coverage.version_parts(pg_version, "tested PostgreSQL version")
                <= coverage.version_parts(high, "archive range")):
            _fail("tested PostgreSQL version is outside the extension archive range")
    core_name = f"postgresql-{pg_version}-{platform}.tar.gz"
    archive_claims = receipt["archives"]
    if not isinstance(archive_claims, dict) or set(archive_claims) != {extension_name, core_name}:
        _fail("archives must identify exactly the extension and assembled PostgreSQL archives")
    digests = {}
    for name, directory in ((extension_name, archives), (core_name, core_archives)):
        claimed = archive_claims[name]
        if not isinstance(claimed, str) or not coverage.SHA256.fullmatch(claimed):
            _fail(f"malformed archive checksum for {name}")
        digest = sha256_file(directory / name)
        if digest != claimed.lower():
            _fail(f"receipt checksum does not match {name}")
        _sidecar(directory / f"{name}.sha256", name, digest)
        digests[name] = digest
    _metadata(archives / extension_name, project_name, version, platform,
              match.group(1), selected["sql_names"])
    record = {
        "schema_version": 2, "scope": "publication", "profile_id": profile["profile_id"],
        "profile_revision": receipt["profile_revision"], "test_cases": profile["case_ids"],
        "case_results": results, "test_revision": revision, "ci": ci, "outcome": outcome,
        "sha256": digests[extension_name],
        "assembled_core": {"archive": core_name, "sha256": digests[core_name],
                           "version": pg_version},
        "project": project, "version": version, "platform": platform,
        "postgresql_version": pg_version,
        "environment": {
            "os": "linux", "os_version": ".".join(map(str, parts)),
            "kernel_release": kernel, "distribution": receipt["distribution"],
            "distribution_version": receipt["distribution_version"],
            "architecture": architecture, "clean_system": receipt["clean_system"],
            "endpoint": endpoint, "image_id": receipt["image_id"],
            "dependency_check_profile": receipt["dependency_check_profile"],
            "dependency_checks_passed": receipt["dependency_checks_passed"],
        },
    }
    records = [{**record, "component": name} for name in selected["sql_names"]]
    for item in records:
        coverage.validate_verification_record(item, support, root)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    for item in records:
        path = output / (f"{item['component']}-{version}-postgresql-{pg_version}-"
                         f"{platform}-{endpoint}-{ci['run_id']}.json")
        path.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.archives, args.core_archives, args.receipt, args.output):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"extension publication record: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
