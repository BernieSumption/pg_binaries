#!/usr/bin/env python3
"""Validate and retain compact Windows pg_cron publication evidence."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coverage
import emit_pgcron_windows_publication as publication


MAX_EVIDENCE_BYTES = 1024 * 1024


def _json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"invalid or missing evidence: {path}") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"evidence must be a JSON object: {path}")
    return value


def _retain(pairs):
    for source, destination in pairs:
        source, destination = Path(source), Path(destination)
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise coverage.CoverageError(f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes")
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    for source, destination in pairs:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def import_run(root, archives, evidence, run_id):
    root, archives, evidence = map(Path, (root, archives, evidence))
    run_id = str(run_id)
    if not run_id.isdigit():
        raise coverage.CoverageError("run ID must be numeric")
    attempt_path = evidence / "publication-attempt.json"
    attempt = _json(attempt_path)
    pg_version = str(attempt.get("postgresql_version", "18.6"))
    if pg_version not in publication.PG_VERSIONS:
        raise coverage.CoverageError("unsupported Windows pg_cron PostgreSQL target")
    profile_id = publication.PROFILE_ID.format(pg_version)
    profile = coverage.verification_profile(root, profile_id)
    if (str(attempt.get("run_id")) != run_id or attempt.get("profile_id") != profile_id
            or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", str(attempt.get("source_revision", "")))
            or not isinstance(attempt.get("steps"), dict)
            or set(attempt["steps"]) != set(publication.CASES)
            or any(value not in {"passed", "failed", "skipped"} for value in attempt["steps"].values())):
        raise coverage.CoverageError("attempt identity or test cases do not match this run")
    retained = root / "support/evidence" / f"pgcron-windows-publication-{run_id}"
    copies = [(attempt_path, retained / attempt_path.name)]
    names = [f"postgresql-{pg_version}-windows-x86_64.tar.gz",
             f"pg_cron-{publication.VERSION}-postgresql-{pg_version}-windows-x86_64.tar.gz"]
    paths = [archives / name for name in names]
    if not all(path.is_file() for path in paths):
        _retain(copies)
        return [str(destination.relative_to(root)) for _, destination in copies]
    digests = {path.name: publication.sha256_file(path) for path in paths}
    for path in paths:
        publication._sidecar(path, digests[path.name])
    expected = digests
    receipt_path = evidence / "publication-receipt.json"
    record_path = evidence / f"{names[1][:-7]}-current-{run_id}.json"
    receipt, record = _json(receipt_path), _json(record_path)
    if (attempt.get("archives") != digests or receipt.get("archives") != digests
            or receipt.get("profile_id") != profile_id
            or receipt.get("profile_revision") != profile["profile_revision"]
            or record.get("sha256") != digests[names[1]]
            or record.get("assembled_core") != {"archive": names[0], "sha256": digests[names[0]], "version": pg_version}
            or record.get("postgresql_version") != pg_version
            or record.get("profile_id") != profile_id
            or record.get("profile_revision") != profile["profile_revision"]
            or record.get("test_revision") != attempt["source_revision"]
            or record.get("case_results") != attempt["steps"]):
        raise coverage.CoverageError("publication evidence does not bind this run and archive bytes")
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    if record.get("outcome") == "passed":
        publication._report(evidence / "static-analysis.json", expected, "PE static analysis")
        symbol_index = _json(evidence / "debug-symbols-index.json")
        entries = symbol_index.get("files", [])
        if ({item.get("archive") for item in entries if isinstance(item, dict)} != set(names)
                or any(item.get("archive_sha256") != digests.get(item.get("archive"))
                       for item in entries if isinstance(item, dict))):
            raise coverage.CoverageError("symbol index does not bind both final archives")
        if (receipt.get("reports", {}).get("archive-suite")
                != publication.sha256_file(evidence / "probe-output.txt")):
            raise coverage.CoverageError("receipt does not bind the pg_cron probe output")
        for key, name in (("static-analysis", "static-analysis.json"),
                          ("symbols", "debug-symbols-index.json")):
            if receipt.get("reports", {}).get(key) != publication.sha256_file(evidence / name):
                raise coverage.CoverageError(f"receipt does not bind {name}")
    copies.append((receipt_path, retained / receipt_path.name))
    for name in ("static-analysis.json", "debug-symbols-index.json", "probe-output.txt"):
        if (evidence / name).is_file():
            copies.append((evidence / name, retained / name))
    copies.append((record_path, root / "support/verification" / record_path.name))
    _retain(copies)
    return [str(destination.relative_to(root)) for _, destination in copies]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.archives, args.evidence, args.run_id)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_cron Windows publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
