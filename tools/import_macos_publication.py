#!/usr/bin/env python3
"""Validate and retain archive-bound macOS publication evidence from CI artifacts."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import coverage
from emit_macos_publication_records import _archive_revision

ARCHITECTURES = {"x86_64", "arm64"}
MAX_EVIDENCE_BYTES = 1024 * 1024
CASES = {"archive-suite", "symbols", "diagnostics"}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path):
    value = coverage.load_json(Path(path))
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"{path}: expected a JSON object")
    return value


def _sidecar(archive, digest):
    sidecar = Path(f"{archive}.sha256")
    lines = sidecar.read_text(encoding="utf-8").splitlines()
    name = Path(archive).name
    if (len(lines) != 1 or not re.fullmatch(rf"[0-9a-fA-F]{{64}}\s+\*?{re.escape(name)}", lines[0])
            or lines[0].split()[0].lower() != digest):
        raise coverage.CoverageError(f"checksum sidecar does not match {name}")


def _report_archives(report, digests, label):
    claims = report.get("archives")
    if isinstance(claims, list):
        try:
            claims = {item["basename"]: item["sha256"] for item in claims}
        except (KeyError, TypeError):
            claims = None
    if not isinstance(claims, dict) or claims != digests:
        raise coverage.CoverageError(f"{label} report archive hashes do not match downloaded archives")


def _attempt(path, run_id):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_EVIDENCE_BYTES:
        raise coverage.CoverageError(f"attempt must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {path}")
    attempt = _json(path)
    steps = attempt.get("steps")
    revision = attempt.get("source_revision")
    if (str(attempt.get("run_id")) != run_id
            or not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", str(revision))
            or not isinstance(steps, dict) or set(steps) != CASES
            or any(value not in {"success", "failure", "skipped"} for value in steps.values())):
        raise coverage.CoverageError("publication attempt identity or case outcomes do not match run/profile")
    results = {case: {"success": "passed", "failure": "failed", "skipped": "skipped"}[value]
               for case, value in steps.items()}
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    return attempt, results, outcome, revision


def _retain_attempt(root, path, run_id, architecture):
    destination = root / "support/evidence" / f"macos-publication-{run_id}" / architecture / path.name
    if destination.exists() and destination.read_bytes() != path.read_bytes():
        raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copyfile(path, destination)
    return [str(destination.relative_to(root))]


def import_run(root, core_artifact, verification_artifact, run_id, architecture,
               postgresql_version="18.6"):
    root, core_artifact, verification_artifact = map(Path, (root, core_artifact, verification_artifact))
    run_id = str(run_id)
    if not re.fullmatch(r"\d+", run_id) or architecture not in ARCHITECTURES:
        raise coverage.CoverageError("run_id must be numeric and architecture must be x86_64 or arm64")
    if not re.fullmatch(r"\d+\.\d+", postgresql_version):
        raise coverage.CoverageError("PostgreSQL version must be major.minor")
    support = coverage.load_json(root / "support.json")
    profile_id = f"macos-publication-current-{architecture}"
    profile = coverage.verification_profile(root, profile_id)
    platform = f"macos-{architecture}"
    if profile["scope"] != "publication" or platform not in profile["platforms"] or set(profile["case_ids"]) != CASES:
        raise coverage.CoverageError("registered profile does not match macOS publication cases and platform")

    attempt_path = verification_artifact / "publication-attempt.json"
    attempt, results, outcome, revision = _attempt(attempt_path, run_id)
    record_dir = verification_artifact / "publication"
    records = sorted(record_dir.glob("*.json")) if record_dir.is_dir() else []
    names = [f"postgresql-{postgresql_version}-{platform}.tar.gz",
             f"pgvector-0.8.7-postgresql-{postgresql_version}-{platform}.tar.gz"]
    archive_paths = [core_artifact / name for name in names]
    archives_complete = all(not path.is_symlink() and path.is_file() for path in archive_paths)
    if outcome in {"failed", "skipped"} and (not archives_complete or not records):
        return _retain_attempt(root, attempt_path, run_id, architecture)
    if not archives_complete:
        missing = next(path.name for path in archive_paths if path.is_symlink() or not path.is_file())
        raise coverage.CoverageError(f"missing downloaded final archive {missing}")
    digests = {}
    for archive in archive_paths:
        name = archive.name
        digests[name] = _sha256(archive)
        _sidecar(archive, digests[name])
    build_revisions = {
        names[0]: _archive_revision(archive_paths[0], "postgresql/manifest.json", "PostgreSQL"),
        names[1]: _archive_revision(archive_paths[1], "metadata.json", "pgvector"),
    }
    run_url = f"https://github.com/{_repository_from_records(verification_artifact)}/actions/runs/{run_id}"
    if len(records) != 2:
        raise coverage.CoverageError("expected PostgreSQL and pgvector publication records")
    expected_components = {"postgresql": names[0], "vector": names[1]}
    if {_json(path).get("component") for path in records} != set(expected_components):
        raise coverage.CoverageError("publication records must contain PostgreSQL and pgvector exactly once")
    copies = [(attempt_path, root / "support/evidence" / f"macos-publication-{run_id}" / architecture / attempt_path.name)]
    for report_name, label in (("static-analysis.json", "static analysis"), ("diagnostics.json", "diagnostic")):
        report_path = verification_artifact / report_name
        if report_path.is_file():
            report = _json(report_path)
            _report_archives(report, digests, label)
            if report.get("architecture") != architecture:
                raise coverage.CoverageError(f"{label} report architecture differs from requested platform")
            if label == "static analysis" and outcome == "passed" and (report.get("passed") is not True or not report.get("inspected_files")):
                raise coverage.CoverageError("passing static analysis report is incomplete")
            if label == "diagnostic" and outcome == "passed" and (
                    report.get("platform") != "macos" or report.get("postgresql_version") != postgresql_version
                    or report.get("pgvector_version") != "0.8.7"):
                raise coverage.CoverageError("diagnostic report identity differs from publication")
            copies.append((report_path, root / "support/evidence" / f"macos-publication-{run_id}" / architecture / report_name))
        elif outcome == "passed":
            raise coverage.CoverageError(f"passing run is missing {label} report")

    for path in records:
        record = _json(path)
        coverage.validate_verification_record(record, support, root)
        component = record.get("component")
        archive_name = expected_components.get(component)
        expected_version = postgresql_version if component == "postgresql" else "0.8.7"
        build_revision = build_revisions[archive_name] if archive_name else None
        ci = {"provider": "github-actions", "run_id": run_id, "run_url": run_url,
              "source_revision": build_revision, "build_revision": build_revision,
              "test_revision": revision}
        expected = {"scope": "publication", "profile_id": profile_id,
                    "test_cases": profile["case_ids"],
                    "case_results": results, "outcome": outcome, "platform": platform,
                    "postgresql_version": postgresql_version, "version": expected_version,
                    "sha256": digests.get(archive_name), "ci": ci, "test_revision": revision}
        if (archive_name is None or record.get("profile_revision") not in profile["compatible_profile_revisions"]
                or any(record.get(key) != value for key, value in expected.items())):
            raise coverage.CoverageError(f"{path}: record identity, profile, outcome, revision, or archive hash mismatch")
        expected_name = f"{archive_name[:-7]}-current-{run_id}.json"
        if path.name != expected_name:
            raise coverage.CoverageError(f"{path}: filename does not match archive and run identity")
        if component == "vector":
            if record.get("project") != "pgvector" or record.get("assembled_core") != {
                    "archive": names[0], "sha256": digests[names[0]], "version": postgresql_version}:
                raise coverage.CoverageError(f"{path}: assembled PostgreSQL archive claim is incorrect")
        elif component != "postgresql":
            raise coverage.CoverageError(f"{path}: unexpected publication component")
        if record.get("environment", {}).get("architecture") != architecture:
            raise coverage.CoverageError(f"{path}: record architecture mismatch")
        copies.append((path, root / "support/verification" / path.name))

    for source, destination in copies:
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise coverage.CoverageError(f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {source}")
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
    return [str(destination.relative_to(root)) for _, destination in copies]


def _repository_from_records(directory):
    # The workflow artifact has no repository field; provenance is fixed by the record run URL.
    candidates = sorted((directory / "publication").glob("*.json"))
    if candidates:
        record = _json(candidates[0])
        url = record.get("ci", {}).get("run_url", "")
        match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/actions/runs/\d+", url)
        if match:
            return match.group(1)
    raise coverage.CoverageError("publication records must identify their GitHub Actions repository")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-artifact", type=Path, required=True)
    parser.add_argument("--verification-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    parser.add_argument("--postgresql-version", default="18.6")
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact, args.verification_artifact,
                                   args.run_id, args.architecture, args.postgresql_version)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"macOS publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
