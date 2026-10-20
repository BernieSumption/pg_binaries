#!/usr/bin/env python3
"""Validate and retain compact Windows pg_ivm publication evidence."""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coverage
import emit_pg_ivm_windows_publication as publication


def _json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"evidence must be an object: {path}")
    return value


def _copy(pairs):
    for src, dst in pairs:
        src, dst = Path(src), Path(dst)
        if src.is_symlink() or not src.is_file() or src.stat().st_size > 1024 * 1024:
            raise coverage.CoverageError("retained evidence must be a regular file under 1 MiB")
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {dst}")
    for src, dst in pairs:
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def import_run(root, archives, evidence, run):
    root, archives, evidence = map(Path, (root, archives, evidence))
    attempt_path = evidence / "publication-attempt.json"
    attempt = _json(attempt_path)
    run = str(run)
    if not run.isdigit() or str(attempt.get("run_id")) != run or attempt.get("profile_id") != f"pgivm-publication-windows-x86_64-{attempt.get('postgresql_version')}":
        raise coverage.CoverageError("attempt identity does not match this run")
    pg = attempt["postgresql_version"]
    names = [f"postgresql-{pg}-windows-x86_64.tar.gz", f"pg_ivm-1.16-postgresql-{pg}-windows-x86_64.tar.gz"]
    dest = root / "support/evidence" / f"pgivm-windows-publication-{run}"
    pairs = [(attempt_path, dest / attempt_path.name)]
    paths = [archives / name for name in names]
    if all(path.is_file() for path in paths):
        digests = {path.name: publication.sha(path) for path in paths}
        if digests[names[0]] != attempt.get("checked_core_sha256") or attempt.get("archives") != digests:
            raise coverage.CoverageError("attempt does not bind checked core and final archive bytes")
        for path in paths:
            lines = Path(str(path) + ".sha256").read_text(encoding="ascii").splitlines()
            if (len(lines) != 1 or not re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?([^\s]+)", lines[0])
                    or lines[0].split()[0].lower() != digests[path.name]
                    or lines[0].split()[-1].lstrip("*") != path.name):
                raise coverage.CoverageError("archive checksum sidecar mismatch")
        receipt_path = evidence / "publication-receipt.json"
        record_path = evidence / f"{names[1][:-7]}-current-{run}.json"
        receipt, record = _json(receipt_path), _json(record_path)
        profile = coverage.verification_profile(root, attempt["profile_id"])
        if (receipt.get("archives") != digests or receipt.get("checked_core_sha256") != digests[names[0]]
                or receipt.get("profile_revision") != profile["profile_revision"]
                or record.get("sha256") != digests[names[1]] or record.get("assembled_core", {}).get("sha256") != digests[names[0]]
                or record.get("profile_id") != attempt["profile_id"] or record.get("profile_revision") != profile["profile_revision"]
                or record.get("case_results") != attempt.get("steps") or record.get("test_revision") != attempt.get("source_revision")):
            raise coverage.CoverageError("record and receipt do not bind the attempt and archive bytes")
        coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
        if record["outcome"] == "passed":
            report_path = evidence / "static-analysis.json"
            report = _json(report_path)
            listed = report.get("archives")
            if isinstance(listed, list):
                listed = {item.get("basename"): item.get("sha256") for item in listed if isinstance(item, dict)}
            if report.get("outcome") != "passed" or listed != digests or receipt.get("reports", {}).get("static-analysis") != publication.sha(report_path):
                raise coverage.CoverageError("static analysis does not bind the final archives")
        pairs += [(receipt_path, dest / receipt_path.name), (record_path, root / "support/verification" / record_path.name)]
    for name in ("static-analysis.json",):
        if (evidence / name).is_file(): pairs.append((evidence / name, dest / name))
    _copy(pairs)
    return [str(dst.relative_to(root)) for _, dst in pairs]


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--archives", type=Path, required=True); p.add_argument("--evidence", type=Path, required=True); p.add_argument("--run-id", required=True); a = p.parse_args()
    try:
        print("\n".join(import_run(a.root, a.archives, a.evidence, a.run_id))); return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"pg_ivm Windows evidence import: {exc}", file=sys.stderr); return 2


if __name__ == "__main__": sys.exit(main())
