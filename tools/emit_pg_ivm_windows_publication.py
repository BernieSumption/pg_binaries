#!/usr/bin/env python3
"""Bind selected Windows pg_ivm checks to the final archive bytes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coverage

CASES = ["archive-suite", "static-analysis"]
VERSIONS = ("15.19", "16.15", "17.11", "18.6")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def emit(root, archives, output, reports, results, revision, core_pin, pg, os_version, image_id, env=None):
    root, archives, output = map(Path, (root, archives, output))
    env = os.environ if env is None else env
    if pg not in VERSIONS or not re.fullmatch(r"[0-9a-f]{64}", core_pin):
        raise coverage.CoverageError("invalid selected target or checked core pin")
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", revision):
        raise coverage.CoverageError("test revision must be a full Git commit hash")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version or "") or not image_id:
        raise coverage.CoverageError("Windows runner version and image identifier are required")
    run, repo, server = env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_REPOSITORY", ""), env.get("GITHUB_SERVER_URL", "")
    if not run.isdigit() or not repo or not server:
        raise coverage.CoverageError("GitHub Actions run provenance is required")
    profile_id = f"pgivm-publication-windows-x86_64-{pg}"
    profile = coverage.verification_profile(root, profile_id)
    if profile["scope"] != "publication" or profile["platforms"] != ["windows-x86_64"] or profile["case_ids"] != CASES or not profile["sources_available"]:
        raise coverage.CoverageError("registered profile does not match the Windows pg_ivm suite")
    if set(results) != set(CASES) or any(value not in {"passed", "failed", "skipped"} for value in results.values()):
        raise coverage.CoverageError("results must identify every profile case")
    names = [f"postgresql-{pg}-windows-x86_64.tar.gz", f"pg_ivm-1.16-postgresql-{pg}-windows-x86_64.tar.gz"]
    paths = [archives / name for name in names]
    output.mkdir(parents=True, exist_ok=True)
    attempt = {"schema_version": 1, "run_id": run, "source_revision": revision,
               "profile_id": profile_id, "postgresql_version": pg, "checked_core_sha256": core_pin,
               "steps": results, "archives_present": {p.name: p.is_file() for p in paths}}
    ap = output / "publication-attempt.json"
    ap.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(p.is_file() for p in paths):
        return [ap]
    digests = {p.name: sha(p) for p in paths}
    if digests[names[0]] != core_pin:
        raise coverage.CoverageError("core archive differs from the checked PostgreSQL pin")
    for path in paths:
        lines = Path(str(path) + ".sha256").read_text(encoding="ascii").splitlines()
        if len(lines) != 1 or not re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^\s]+)", lines[0]) or lines[0].split()[-1].lstrip("*") != path.name or lines[0].split()[0].lower() != digests[path.name]:
            raise coverage.CoverageError(f"invalid checksum sidecar for {path.name}")
    attempt["archives"] = digests
    ap.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if all(value == "passed" for value in results.values()):
        report = json.loads(Path(reports["static-analysis"]).read_text(encoding="utf-8-sig"))
        actual = report.get("archives")
        if isinstance(actual, list):
            actual = {item.get("basename"): item.get("sha256") for item in actual if isinstance(item, dict)}
        if report.get("outcome") != "passed" or actual != digests:
            raise coverage.CoverageError("PE report does not identify the final archive bytes")
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    record = {"schema_version": 2, "scope": "publication", "profile_id": profile_id,
              "profile_revision": profile["profile_revision"], "test_cases": CASES, "case_results": results,
              "test_revision": revision, "ci": {"provider": "github-actions", "run_id": run,
              "run_url": f"{server.rstrip('/')}/{repo}/actions/runs/{run}", "source_revision": revision,
              "build_revision": revision, "test_revision": revision}, "outcome": outcome,
              "sha256": digests[names[1]], "component": "pg_ivm", "project": "pg_ivm", "version": "1.16",
              "platform": "windows-x86_64", "postgresql_version": pg,
              "assembled_core": {"archive": names[0], "sha256": digests[names[0]], "version": pg},
              "prerequisite_archives": [], "environment": {"os": "windows", "os_version": os_version,
              "architecture": "x86_64", "clean_system": True, "endpoint": "current", "image_id": image_id,
              "dependency_check_profile": "windows-pe-runtime-v1", "dependency_checks_passed": results["static-analysis"] == "passed"}}
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    rp = output / f"{names[1][:-7]}-current-{run}.json"
    rp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {"schema_version": 1, "profile_id": profile_id, "profile_revision": profile["profile_revision"],
               "archives": digests, "checked_core_sha256": core_pin, "case_results": results,
               "reports": {key: sha(path) for key, path in reports.items() if Path(path).is_file()}}
    (output / "publication-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [ap, output / "publication-receipt.json", rp]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--archives", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True); p.add_argument("--results", type=Path, required=True)
    p.add_argument("--revision", required=True); p.add_argument("--core-sha256", required=True)
    p.add_argument("--os-version", required=True); p.add_argument("--image-id", required=True)
    p.add_argument("--postgresql-version", choices=VERSIONS, required=True); a = p.parse_args()
    try:
        result = json.loads(a.results.read_text(encoding="utf-8-sig"))
        files = emit(a.root, a.archives, a.output, {"static-analysis": a.report}, result, a.revision,
                     a.core_sha256, a.postgresql_version, a.os_version, a.image_id)
        print("\n".join(map(str, files))); return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_ivm Windows evidence: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    sys.exit(main())
