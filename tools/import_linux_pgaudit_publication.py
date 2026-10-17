#!/usr/bin/env python3
"""Validate and retain archive-bound pgAudit Linux publication evidence."""

import argparse
from pathlib import Path
import re
import shutil
import sys

import coverage
from import_linux_publication_run import _case_results, _outcome, _sha256, _static_analysis, _steps
from import_linux_tiger_publication import _sidecar


ARCHITECTURES = {"x86_64", "arm64"}
PGAUDIT_VERSION = "18.0"
MAX_EVIDENCE_BYTES = 1024 * 1024
STEP_NAMES = {"core_build", "pgaudit_build", "pgaudit_verify"}


def _attempt(path, run_id, architecture, postgresql_version):
    attempt = coverage.load_json(path)
    if (not isinstance(attempt, dict) or attempt.get("schema_version") != 1
            or str(attempt.get("run_id")) != run_id
            or attempt.get("architecture") != architecture
            or attempt.get("postgresql_version") != postgresql_version
            or attempt.get("pgaudit_version") != PGAUDIT_VERSION
            or not coverage.REVISION.fullmatch(str(attempt.get("source_revision", "")))):
        raise coverage.CoverageError("attempt identity does not match this PostgreSQL run")
    steps = attempt.get("steps")
    if (not isinstance(steps, dict) or set(steps) != STEP_NAMES
            or any(value not in {"success", "failure", "skipped"} for value in steps.values())):
        raise coverage.CoverageError("attempt must record each core and pgAudit step outcome")
    image = attempt.get("verifier_image_id")
    if image != "unknown" and not re.fullmatch(r"sha256:[0-9a-f]{64}", str(image)):
        raise coverage.CoverageError("attempt verifier image identity is malformed")
    build, verify = steps["pgaudit_build"], steps["pgaudit_verify"]
    suite = ("failure" if "failure" in (build, verify) or
             (build == verify == "success" and image == "unknown") else
             "success" if build == verify == "success" else "skipped")
    return attempt, suite


def import_run(root, core_artifact, pgaudit_artifact, run_id, architecture,
               postgresql_version="18.6"):
    root, core_artifact, pgaudit_artifact = map(Path, (root, core_artifact, pgaudit_artifact))
    run_id = str(run_id)
    if (not re.fullmatch(r"\d+", run_id) or architecture not in ARCHITECTURES
            or not re.fullmatch(r"\d+\.\d+", postgresql_version)
            or postgresql_version != "18.6"):
        raise coverage.CoverageError("expected numeric run_id, PostgreSQL 18.6, and x86_64 or arm64")
    support = coverage.load_json(root / "support.json")
    snapshot = coverage.load_json(root / "support/postgresql-releases.json")
    if postgresql_version not in coverage.release_snapshot(snapshot, support):
        raise coverage.CoverageError(f"PostgreSQL {postgresql_version} is not selected")
    version = support["extensions"]["pgaudit"]["versions"].get(PGAUDIT_VERSION)
    if not isinstance(version, dict) or version.get("postgresql_minimum_major") != 18:
        raise coverage.CoverageError("pgAudit 18.0 is not declared for PostgreSQL 18")

    platform = f"linux-{architecture}"
    profile_id = f"pgaudit-publication-current-{architecture}"
    profile = coverage.verification_profile(root, profile_id)
    if profile["scope"] != "publication" or platform not in profile["platforms"]:
        raise coverage.CoverageError("profile does not match the Linux publication platform")

    publication = pgaudit_artifact / "pgaudit-publication"
    target = root / "support/evidence" / f"pgaudit-publication-{run_id}" / architecture
    steps_path, attempt_path = publication / "current-steps.json", publication / "attempt.json"
    steps = _steps(steps_path, profile)
    attempt, expected_suite = _attempt(attempt_path, run_id, architecture, postgresql_version)
    if len(profile["case_ids"]) != 1 or steps != {profile["case_ids"][0]: expected_suite}:
        raise coverage.CoverageError("publication case outcome differs from raw attempt outcomes")

    core_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    extension_name = f"pgaudit-{PGAUDIT_VERSION}-postgresql-{postgresql_version}-{platform}.tar.gz"
    core_candidates = (core_artifact / core_name, core_artifact / "pilot" / core_name,
                       pgaudit_artifact / core_name)
    core_archive = next((path for path in core_candidates if path.is_file()), core_candidates[0])
    archives = [core_archive, pgaudit_artifact / extension_name]
    records = sorted((publication / "records").glob("*.json"))
    receipt_path = publication / "current-receipt.json"
    receipt = coverage.load_json(receipt_path) if receipt_path.is_file() else None
    archive_bound = receipt is not None or bool(records)
    digests = {}
    if archive_bound and not all(path.is_file() for path in archives):
        raise coverage.CoverageError("receipt or records exist but referenced archives are missing")
    for path in archives:
        if path.is_file():
            digest = _sha256(path)
            sidecar = path.with_name(path.name + ".sha256")
            if archive_bound or sidecar.exists():
                _sidecar(path, digest)
            digests[path.name] = digest

    copies = [(steps_path, target / steps_path.name), (attempt_path, target / attempt_path.name)]
    if receipt is not None:
        ci, revision = receipt.get("ci", {}), receipt.get("test_revision")
        expected = {
            "profile_id": profile_id, "project": "pgaudit", "version": PGAUDIT_VERSION,
            "postgresql_version": postgresql_version, "architecture": architecture,
            "endpoint": "current", "case_results": _case_results(steps),
            "archives": digests, "extension_archive": extension_name,
            "prerequisite_archives": [],
        }
        if (any(receipt.get(key) != value for key, value in expected.items())
                or receipt.get("profile_revision") not in profile["compatible_profile_revisions"]
                or not isinstance(ci, dict) or ci.get("run_id") != run_id
                or ci.get("provider") != "github-actions"
                or not str(ci.get("run_url", "")).startswith("https://github.com/")
                or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")
                or revision != attempt["source_revision"]
                or not coverage.REVISION.fullmatch(str(revision))
                or any(ci.get(key) != revision for key in ("source_revision", "build_revision", "test_revision"))):
            raise coverage.CoverageError("receipt identity, archives, profile or outcomes do not match attempt")
        if (receipt.get("distribution") != "Alpine Linux"
                or not re.fullmatch(r"3\.22(?:\.\d+)?", str(receipt.get("distribution_version")))
                or not receipt.get("kernel_release")
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(receipt.get("image_id")))
                or receipt.get("image_id") != attempt.get("verifier_image_id")
                or receipt.get("dependency_check_profile") != "pgaudit-runtime-v1"):
            raise coverage.CoverageError("receipt must identify the matching Alpine 3.22 verifier, kernel and image")
        if _outcome(receipt["case_results"]) == "passed" and (
                receipt.get("clean_system") is not True
                or receipt.get("dependency_checks_passed") is not True):
            raise coverage.CoverageError("passed receipt requires a clean system and successful dependency checks")
        copies.append((receipt_path, target / receipt_path.name))

    if records and receipt is None:
        raise coverage.CoverageError("records require matching receipt")
    if receipt is not None and not records:
        raise coverage.CoverageError("receipt requires its archive-bound pgAudit record")
    if len(records) > 1:
        raise coverage.CoverageError("expected one pgAudit record")
    for source in records:
        record = coverage.load_json(source)
        coverage.validate_verification_record(record, support, root)
        expected = {
            "profile_id": profile_id, "profile_revision": receipt["profile_revision"],
            "component": "pgaudit", "project": "pgaudit", "version": PGAUDIT_VERSION,
            "postgresql_version": postgresql_version, "platform": platform,
            "case_results": _case_results(steps), "outcome": _outcome(_case_results(steps)),
            "test_cases": profile["case_ids"], "ci": receipt["ci"],
            "test_revision": receipt["test_revision"], "sha256": digests[extension_name],
            "assembled_core": {"archive": core_name, "sha256": digests[core_name],
                               "version": postgresql_version},
            "prerequisite_archives": [],
        }
        if (any(record.get(key) != value for key, value in expected.items())
                or source.name != f"pgaudit-{PGAUDIT_VERSION}-postgresql-{postgresql_version}-"
                                 f"{platform}-current-{run_id}.json"
                or any(record.get("environment", {}).get(key) != receipt.get(key) for key in (
                    "endpoint", "architecture", "kernel_release", "distribution",
                    "distribution_version", "image_id", "clean_system",
                    "dependency_check_profile", "dependency_checks_passed"))):
            raise coverage.CoverageError("record identity or archive checksum differs from receipt")
        copies.append((source, root / "support/verification" / source.name))

    passed = receipt is not None and _outcome(receipt["case_results"]) == "passed"
    report = _static_analysis(pgaudit_artifact / "static-analysis/pgaudit.json", architecture,
                              digests, passed)
    if report is not None:
        copies.append((report, target / "static-analysis" / report.name))
    for source in sorted(publication.rglob("*.log")):
        copies.append((source, target / source.relative_to(publication)))
    for source, destination in copies:
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise coverage.CoverageError(
                f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {source}")
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
    parser.add_argument("--pgaudit-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    parser.add_argument("--postgresql-version", default="18.6")
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact, args.pgaudit_artifact,
                                   args.run_id, args.architecture, args.postgresql_version)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux pgAudit publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
