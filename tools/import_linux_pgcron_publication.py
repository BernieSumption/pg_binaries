#!/usr/bin/env python3
"""Validate and retain archive-bound pg_cron Linux publication evidence."""

import argparse
from pathlib import Path
import re
import shutil
import sys

import coverage
from import_linux_publication_run import _case_results, _outcome, _sha256, _static_analysis, _steps
from import_linux_tiger_publication import _sidecar


ARCHITECTURES = {"x86_64", "arm64"}
DEFAULT_PG_VERSION = "18.6"
MAX_EVIDENCE_BYTES = 1024 * 1024
STEP_NAMES = {"core_build", "pgcron_build", "pgcron_verify"}


def _selected_version(support, releases, postgresql_version, platform):
    _, targets = coverage.expected_targets(support, releases)
    versions = {version for name, version, pg_version, target_platform in targets
                if name == "pg_cron" and pg_version == postgresql_version
                and target_platform == platform}
    if len(versions) != 1:
        raise coverage.CoverageError(
            f"pg_cron must have exactly one selected version for PostgreSQL "
            f"{postgresql_version} on {platform}")
    return next(iter(versions))


def import_run(root, core_artifact, pgcron_artifact, run_id, architecture,
               postgresql_version=DEFAULT_PG_VERSION):
    root, core_artifact, pgcron_artifact = map(Path, (root, core_artifact, pgcron_artifact))
    run_id = str(run_id)
    if not re.fullmatch(r"\d+", run_id) or architecture not in ARCHITECTURES:
        raise coverage.CoverageError("expected numeric run_id and x86_64 or arm64 architecture")
    support = coverage.load_json(root / "support.json")
    snapshot = coverage.load_json(root / "support/postgresql-releases.json")
    releases = coverage.release_snapshot(snapshot, support)
    if postgresql_version not in releases:
        raise coverage.CoverageError(f"PostgreSQL {postgresql_version} is not selected")
    profile_id = f"pgcron-publication-current-{architecture}"
    profile = coverage.verification_profile(root, profile_id)
    platform = f"linux-{architecture}"
    version = _selected_version(support, releases, postgresql_version, platform)
    if profile["scope"] != "publication" or platform not in profile["platforms"]:
        raise coverage.CoverageError("profile does not match the Linux publication platform")

    publication = pgcron_artifact / "pgcron-publication"
    extension_dir = pgcron_artifact / "pg_cron"
    if not extension_dir.is_dir():
        extension_dir = pgcron_artifact
    steps_path, attempt_path = publication / "current-steps.json", publication / "attempt.json"
    steps = _steps(steps_path, profile)
    attempt = coverage.load_json(attempt_path)
    if (not isinstance(attempt, dict) or attempt.get("schema_version") != 1
            or str(attempt.get("run_id")) != run_id
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))
            or attempt.get("architecture") != architecture
            or attempt.get("postgresql_version") != postgresql_version
            or attempt.get("pg_cron_version") != version
            or not isinstance(attempt.get("steps"), dict)
            or set(attempt["steps"]) != STEP_NAMES
            or any(value not in {"success", "failure", "skipped"} for value in attempt["steps"].values())):
        raise coverage.CoverageError("attempt identity or step outcomes are invalid")
    image = attempt.get("verifier_image_id")
    if image != "unknown" and not re.fullmatch(r"sha256:[0-9a-f]{64}", str(image)):
        raise coverage.CoverageError("verifier image identity is malformed")
    build, verify = attempt["steps"]["pgcron_build"], attempt["steps"]["pgcron_verify"]
    suite = ("failure" if "failure" in (build, verify) or
             (build == verify == "success" and image == "unknown") else
             "success" if build == verify == "success" else "skipped")
    if (set(profile["case_ids"]) != {"pgcron-archive-suite"}
            or steps != {"pgcron-archive-suite": suite}):
        raise coverage.CoverageError("publication case outcome differs from raw attempt outcomes")

    core_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    extension_name = f"pg_cron-{version}-postgresql-{postgresql_version}-{platform}.tar.gz"
    archives = [core_artifact / "pilot" / core_name, extension_dir / extension_name]
    records = sorted((publication / "records").glob("*.json"))
    receipt_path = publication / "current-receipt.json"
    receipt = coverage.load_json(receipt_path) if receipt_path.is_file() else None
    bound = receipt is not None or bool(records)
    digests = {}
    for archive in archives:
        if archive.is_file():
            digests[archive.name] = _sha256(archive)
            if bound or archive.with_name(archive.name + ".sha256").exists():
                _sidecar(archive, digests[archive.name])
    if bound and (len(digests) != 2 or set(digests) != {core_name, extension_name}):
        raise coverage.CoverageError("receipt or records exist but referenced archives are missing")

    target = root / "support/evidence" / f"pgcron-publication-{run_id}" / architecture
    copies = [(steps_path, target / steps_path.name), (attempt_path, target / attempt_path.name)]
    if receipt is not None:
        ci = receipt.get("ci", {})
        revision = receipt.get("test_revision")
        expected = {"profile_id": profile_id, "project": "pg_cron", "version": version,
                    "postgresql_version": postgresql_version, "architecture": architecture,
                    "endpoint": "current", "case_results": _case_results(steps),
                    "archives": digests, "extension_archive": extension_name,
                    "prerequisite_archives": []}
        if (any(receipt.get(key) != value for key, value in expected.items())
                or receipt.get("profile_revision") not in profile["compatible_profile_revisions"]
                or not isinstance(ci, dict) or ci.get("run_id") != run_id
                or ci.get("provider") != "github-actions"
                or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")
                or revision != attempt.get("source_revision")
                or any(ci.get(key) != revision for key in ("source_revision", "build_revision", "test_revision"))):
            raise coverage.CoverageError("receipt identity, archive hashes, profile or outcomes do not match attempt")
        if (receipt.get("distribution") != "Alpine Linux"
                or not re.fullmatch(r"3\.22(?:\.\d+)?", str(receipt.get("distribution_version")))
                or not receipt.get("kernel_release") or receipt.get("image_id") != image
                or receipt.get("dependency_check_profile") != "pg_cron-runtime-v1"):
            raise coverage.CoverageError("receipt must identify the matching Alpine 3.22 verifier and runtime check")
        if _outcome(receipt["case_results"]) == "passed" and not (
                receipt.get("clean_system") is True and receipt.get("dependency_checks_passed") is True):
            raise coverage.CoverageError("passed receipt requires clean runtime and dependency checks")
        copies.append((receipt_path, target / receipt_path.name))
    if records and receipt is None:
        raise coverage.CoverageError("records require matching receipt")
    if len(records) > 1:
        raise coverage.CoverageError("expected one pg_cron record")
    for source in records:
        record = coverage.load_json(source)
        coverage.validate_verification_record(record, support, root)
        results = _case_results(steps)
        expected = {"profile_id": profile_id, "component": "pg_cron", "project": "pg_cron",
                    "version": version, "postgresql_version": postgresql_version,
                    "platform": platform, "case_results": results, "outcome": _outcome(results),
                    "test_cases": profile["case_ids"], "ci": receipt["ci"],
                    "test_revision": receipt["test_revision"], "sha256": digests[extension_name],
                    "assembled_core": {"archive": core_name, "sha256": digests[core_name],
                                       "version": postgresql_version}, "prerequisite_archives": []}
        if (any(record.get(key) != value for key, value in expected.items())
                or source.name != f"pg_cron-{version}-postgresql-{postgresql_version}-{platform}-current-{run_id}.json"
                or record.get("profile_revision") != receipt.get("profile_revision")
                or any(record.get("environment", {}).get(key) != receipt.get(key) for key in (
                    "endpoint", "architecture", "kernel_release", "distribution",
                    "distribution_version", "image_id", "clean_system",
                    "dependency_check_profile", "dependency_checks_passed"))):
            raise coverage.CoverageError("record identity or archive checksum differs from receipt")
        copies.append((source, root / "support/verification" / source.name))
    passed = receipt is not None and _outcome(receipt["case_results"]) == "passed"
    report = _static_analysis(extension_dir / "static-analysis/pg_cron.json", architecture,
                              digests, passed)
    if report is not None:
        copies.append((report, target / "static-analysis" / report.name))
    for source in sorted(publication.rglob("*.log")):
        copies.append((source, target / source.relative_to(publication)))
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
    parser.add_argument("--pgcron-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    parser.add_argument("--postgresql-version", default=DEFAULT_PG_VERSION,
                        help="selected exact PostgreSQL version (defaults to 18.6)")
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact, args.pgcron_artifact,
                                   args.run_id, args.architecture, args.postgresql_version)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux pg_cron publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
