#!/usr/bin/env python3
"""Bind the selected Windows pg_cron checks to the final archive bytes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coverage


PROFILE_ID = "pgcron-publication-windows-x86_64-{}"
CASES = ["archive-suite", "static-analysis", "symbols"]
PG_VERSIONS = ("15.19", "16.15", "17.11", "18.6")
VERSION = "1.6.8"


def _read_json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"{label} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"{label} must be a JSON object")
    return value


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar(path, digest):
    lines = Path(str(path) + ".sha256").read_text(encoding="ascii").splitlines()
    if (len(lines) != 1 or not re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^\s]+)", lines[0])
            or lines[0].split()[-1].lstrip("*") != Path(path).name
            or lines[0].split()[0].lower() != digest):
        raise coverage.CoverageError(f"invalid checksum sidecar for {Path(path).name}")


def _archive_json(path, member_name):
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = [item for item in archive.getmembers()
                       if item.name == member_name and item.isfile() and item.size <= 1024 * 1024]
            if len(members) != 1:
                raise coverage.CoverageError(f"archive requires one bounded {member_name}")
            return json.loads(archive.extractfile(members[0]).read().decode("utf-8"))
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"cannot read {member_name} from {Path(path).name}") from exc


def _report(path, expected, label, passed_key="outcome"):
    value = _read_json(path, label)
    actual = value.get("archives")
    if isinstance(actual, list):
        actual = {item.get("basename"): item.get("sha256") for item in actual if isinstance(item, dict)}
    if actual != expected:
        raise coverage.CoverageError(f"{label} does not identify the final archive bytes")
    if passed_key == "outcome" and value.get("outcome") != "passed":
        raise coverage.CoverageError(f"{label} did not pass")
    return value


def emit(root, archives, output, reports, step_results, revision, os_version, image_id,
         environ=None, pg_version="18.6"):
    root, archives, output = map(Path, (root, archives, output))
    environ = os.environ if environ is None else environ
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", revision):
        raise coverage.CoverageError("test revision must be a full Git commit hash")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version or "") or not image_id:
        raise coverage.CoverageError("Windows runner version and image identifier are required")
    run_id = str(environ.get("GITHUB_RUN_ID", ""))
    repository, server = environ.get("GITHUB_REPOSITORY", ""), environ.get("GITHUB_SERVER_URL", "")
    if not run_id.isdigit() or not repository or not server:
        raise coverage.CoverageError("GitHub Actions run provenance is required")
    if pg_version not in PG_VERSIONS:
        raise coverage.CoverageError("unsupported Windows pg_cron PostgreSQL target")
    profile_id = PROFILE_ID.format(pg_version)
    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or profile["platforms"] != ["windows-x86_64"]
            or profile["case_ids"] != CASES or not profile["sources_available"]):
        raise coverage.CoverageError("registered profile does not match the Windows pg_cron suite")
    if set(step_results) != set(CASES) or any(v not in {"passed", "failed", "skipped"} for v in step_results.values()):
        raise coverage.CoverageError("step results must identify every profile case")

    core_name = f"postgresql-{pg_version}-windows-x86_64.tar.gz"
    extension_name = f"pg_cron-{VERSION}-postgresql-{pg_version}-windows-x86_64.tar.gz"
    names = [core_name, extension_name]
    paths = [archives / name for name in names]
    output.mkdir(parents=True, exist_ok=True)
    attempt = {"schema_version": 1, "run_id": run_id, "source_revision": revision,
               "profile_id": profile_id, "postgresql_version": pg_version, "steps": step_results,
               "archives_present": {p.name: p.is_file() for p in paths}}
    attempt_path = output / "publication-attempt.json"
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(p.is_file() for p in paths):
        return [attempt_path]
    digests = {p.name: sha256_file(p) for p in paths}
    for path in paths:
        _sidecar(path, digests[path.name])
    core = _archive_json(paths[0], "postgresql/manifest.json")
    extension = _archive_json(paths[1], "metadata.json")
    if (core.get("component") != "postgresql" or core.get("version") != pg_version
            or core.get("platform") != "windows" or core.get("architecture") != "x86_64"
            or extension.get("project") != "pg_cron" or extension.get("version") != VERSION
            or extension.get("postgresql_version") != pg_version
            or extension.get("platform") != "windows" or extension.get("architecture") != "x86_64"
            or extension.get("core_archive") != {"basename": core_name, "sha256": digests[core_name]}):
        raise coverage.CoverageError("archive metadata does not match the selected pg_cron target")
    attempt["archives"] = digests
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if all(value == "passed" for value in step_results.values()):
        static = _report(reports["static-analysis"], digests, "PE static analysis")
        symbols = _read_json(reports["symbols"], "symbol index")
        symbol_entries = symbols.get("files")
        if (not isinstance(symbol_entries, list) or
                {entry.get("archive") for entry in symbol_entries if isinstance(entry, dict)} != set(names) or
                any(entry.get("archive_sha256") != digests.get(entry.get("archive"))
                    for entry in symbol_entries if isinstance(entry, dict))):
            raise coverage.CoverageError("symbol index does not match both final archives")
        probe = Path(reports["archive-suite"]).read_text(encoding="utf-8")
        if ("installation_relocated=true" not in probe or "job_status=succeeded" not in probe
                or not re.search(r"(?m)^job_rows=[1-9]\d*\s*$", probe)):
            raise coverage.CoverageError("pg_cron probe does not prove relocation and a completed job")
        if static.get("platform") != "windows" or static.get("architecture") != "x86_64" or not static.get("inspected_files"):
            raise coverage.CoverageError("PE static analysis identity is invalid")
    outcome = "passed" if all(value == "passed" for value in step_results.values()) else (
        "failed" if "failed" in step_results.values() else "skipped")
    build_identity = re.fullmatch(r"github-([1-9][0-9]*)-([1-9][0-9]*)", str(extension.get("build_id", "")))
    build_revision = extension.get("source_revision")
    if not build_identity or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", str(build_revision or "")):
        raise coverage.CoverageError("pg_cron archive build provenance is invalid")
    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server.rstrip('/')}/{repository}/actions/runs/{run_id}",
          "source_revision": build_revision, "build_revision": build_revision,
          "test_revision": revision, "build_run_id": build_identity.group(1),
          "build_run_attempt": build_identity.group(2)}
    record = {"schema_version": 2, "scope": "publication", "profile_id": profile_id,
              "profile_revision": profile["profile_revision"], "test_cases": CASES,
              "case_results": step_results, "test_revision": revision, "ci": ci,
              "outcome": outcome, "sha256": digests[extension_name],
              "component": "pg_cron", "project": "pg_cron", "version": VERSION,
              "platform": "windows-x86_64", "postgresql_version": pg_version,
              "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": pg_version},
              "prerequisite_archives": [],
              "environment": {"os": "windows", "os_version": os_version,
                              "architecture": "x86_64", "clean_system": True,
                              "endpoint": "current", "image_id": image_id,
                              "dependency_check_profile": "windows-pe-runtime-v1",
                              "dependency_checks_passed": step_results["static-analysis"] == "passed"}}
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    record_path = output / f"{extension_name[:-7]}-current-{run_id}.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {"schema_version": 1, "profile_id": profile_id,
               "profile_revision": profile["profile_revision"], "archives": digests,
               "case_results": step_results, "ci": ci,
               "reports": {key: sha256_file(value) for key, value in reports.items() if Path(value).is_file()}}
    receipt_path = output / "publication-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [attempt_path, receipt_path, record_path]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--postgresql-version", choices=PG_VERSIONS, default="18.6")
    parser.add_argument("--step-results", type=Path, required=True)
    args = parser.parse_args()
    try:
        results = _read_json(args.step_results, "step results")
        reports = {"static-analysis": args.reports / "static-analysis.json",
                   "symbols": args.reports / "debug-symbols/index.json",
                   "archive-suite": args.reports / "probe-output.txt"}
        for path in emit(args.root, args.archives, args.output, reports, results,
                         args.revision, args.os_version, args.image_id,
                         pg_version=args.postgresql_version):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_cron Windows publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
