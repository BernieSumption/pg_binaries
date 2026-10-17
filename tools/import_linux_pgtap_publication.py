#!/usr/bin/env python3
"""Validate and retain compact pgTAP Linux publication evidence."""

import argparse
from pathlib import Path
import re
import shutil
import sys

import coverage
from import_linux_publication_run import _sha256, _steps, _case_results, _outcome, _static_analysis
from import_linux_tiger_publication import _sidecar

ARCHITECTURES = {"x86_64", "arm64"}
MAX_EVIDENCE_BYTES = 1024 * 1024


def import_run(root, core_artifact, pgtap_artifact, run_id, architecture, postgresql_version="18.6"):
    root, core_artifact, pgtap_artifact = map(Path, (root, core_artifact, pgtap_artifact))
    run_id = str(run_id)
    if (not re.fullmatch(r"\d+", run_id) or architecture not in ARCHITECTURES
            or not re.fullmatch(r"\d+\.\d+", postgresql_version)):
        raise coverage.CoverageError("expected numeric run_id, PostgreSQL version and architecture x86_64 or arm64")
    support = coverage.load_json(root / "support.json")
    snapshot = coverage.load_json(root / "support/postgresql-releases.json")
    if postgresql_version not in coverage.release_snapshot(snapshot, support):
        raise coverage.CoverageError(f"PostgreSQL {postgresql_version} is not selected")
    platform = f"linux-{architecture}"
    profile_id = f"pgtap-publication-current-{architecture}"
    profile = coverage.verification_profile(root, profile_id)
    if profile["scope"] != "publication" or platform not in profile["platforms"]:
        raise coverage.CoverageError("profile does not match publication platform")
    publication = pgtap_artifact / "pgtap-publication"
    extension_dir = pgtap_artifact
    target = root / "support/evidence" / f"pgtap-publication-{run_id}" / architecture
    steps_path = publication / "current-steps.json"
    steps = _steps(steps_path, profile)
    copies = [(steps_path, target / steps_path.name)]
    core_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    extension_name = f"pgtap-1.3.4-postgresql-{postgresql_version}-{platform}.tar.gz"
    archives = [core_artifact / "pilot" / core_name, extension_dir / extension_name]
    records = sorted((publication / "records").glob("*.json"))
    receipt_path = publication / "current-receipt.json"
    receipt = coverage.load_json(receipt_path) if receipt_path.is_file() else None
    digests = {}
    if receipt is not None or records:
        if not all(path.is_file() for path in archives):
            raise coverage.CoverageError("receipt or records exist but referenced archives are missing")
    for path in archives:
        if path.is_file():
            digests[path.name] = _sha256(path)
            _sidecar(path, digests[path.name])
    if receipt is not None:
        ci = receipt.get("ci", {})
        revision = receipt.get("test_revision")
        expected = {"profile_id": profile_id, "project": "pgtap", "version": "1.3.4",
                    "postgresql_version": postgresql_version, "architecture": architecture,
                    "endpoint": "current", "case_results": _case_results(steps),
                    "archives": digests, "extension_archive": extension_name,
                    "prerequisite_archives": []}
        if (any(receipt.get(key) != value for key, value in expected.items())
                or receipt.get("profile_revision") not in profile["compatible_profile_revisions"]
                or not isinstance(ci, dict) or ci.get("run_id") != run_id
                or ci.get("provider") != "github-actions"
                or not str(ci.get("run_url", "")).startswith("https://github.com/")
                or not str(ci.get("run_url", "")).endswith(f"/actions/runs/{run_id}")
                or not re.fullmatch(r"[0-9a-f]{40}", str(revision))
                or any(ci.get(key) != revision for key in ("source_revision", "build_revision", "test_revision"))):
            raise coverage.CoverageError("receipt identity, archives, or outcomes do not match run")
        if (receipt.get("distribution") != "Alpine Linux"
                or not re.fullmatch(r"3\.22(?:\.\d+)?", str(receipt.get("distribution_version")))
                or not receipt.get("kernel_release")
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(receipt.get("image_id")))):
            raise coverage.CoverageError("receipt must identify Alpine 3.22, kernel and image")
        copies.append((receipt_path, target / receipt_path.name))
    if records and receipt is None:
        raise coverage.CoverageError("records require matching receipt")
    if len(records) > 1:
        raise coverage.CoverageError("expected one pgTAP record")
    for source in records:
        record = coverage.load_json(source)
        coverage.validate_verification_record(record, support, root)
        expected = {"profile_id": profile_id, "component": "pgtap", "project": "pgtap",
                    "version": "1.3.4", "postgresql_version": postgresql_version, "platform": platform,
                    "case_results": _case_results(steps), "outcome": _outcome(_case_results(steps)),
                    "test_cases": profile["case_ids"], "ci": receipt["ci"],
                    "test_revision": receipt["test_revision"], "sha256": digests[extension_name],
                    "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": postgresql_version},
                    "prerequisite_archives": []}
        if (any(record.get(key) != value for key, value in expected.items())
                or source.name != f"pgtap-1.3.4-postgresql-{postgresql_version}-{platform}-current-{run_id}.json"
                or any(record.get("environment", {}).get(key) != receipt.get(key) for key in (
                    "endpoint", "architecture", "kernel_release", "distribution", "distribution_version",
                    "image_id", "clean_system", "dependency_check_profile", "dependency_checks_passed"))):
            raise coverage.CoverageError("record identity, archive or environment differs from receipt")
        copies.append((source, root / "support/verification" / source.name))
    passed = receipt is not None and _outcome(receipt["case_results"]) == "passed"
    report = _static_analysis(extension_dir / "static-analysis/pgtap.json", architecture, digests, passed)
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
    parser.add_argument("--pgtap-artifact", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    parser.add_argument("--postgresql-version", default="18.6")
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.core_artifact, args.pgtap_artifact,
                                   args.run_id, args.architecture, args.postgresql_version)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"Linux pgTAP publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
