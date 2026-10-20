#!/usr/bin/env python3
"""Report selected-target coverage in an unpublished structural candidate.

This report checks candidate references and verification records. It does not
check staged archive bytes or establish publication eligibility; run
publication_preflight.py for local archive validation.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_COVERAGE_SPEC = importlib.util.spec_from_file_location(
    "candidate_coverage_base", Path(__file__).with_name("coverage.py"))
_coverage = importlib.util.module_from_spec(_COVERAGE_SPEC)
_COVERAGE_SPEC.loader.exec_module(_coverage)


def candidate_verification_records(candidate, root, support):
    evidence = candidate.get("verification_evidence", {})
    if not isinstance(evidence, dict):
        raise _coverage.CoverageError(
            "candidate verification_evidence must be an object keyed by download URL")
    records = []
    for url, entries in evidence.items():
        if not isinstance(url, str) or not isinstance(entries, list):
            raise _coverage.CoverageError(
                "candidate verification_evidence entries must be arrays keyed by URL")
        for index, record in enumerate(entries):
            if not isinstance(record, dict):
                raise _coverage.CoverageError(
                    f"candidate verification evidence for {url} must contain objects")
            current = _coverage.validate_verification_record(
                record, support, root, f"candidate verification evidence {url}", allow_stale=True)
            record = dict(record)
            record["_profile_current"] = current
            record["_record_file"] = f"candidate:{url}#{index + 1}"
            records.append(record)
    return records


def report_candidate(root, candidate_path):
    root = Path(root)
    candidate = _coverage.load_json(candidate_path)
    if not isinstance(candidate, dict) or candidate.get("candidate_status") != "structural-draft":
        raise _coverage.CoverageError("candidate inventory must have candidate_status 'structural-draft'")
    if candidate.get("schema_version") != 1:
        raise _coverage.CoverageError("candidate inventory schema_version must be 1")

    support = _coverage.load_json(root / "support.json")
    _coverage.validate_support(support)
    _coverage.validate_extension_policy(root, support)
    if candidate.get("os_support") != support["os_support"]:
        raise _coverage.CoverageError("candidate inventory os_support does not match support.json")
    snapshot = _coverage.load_json(root / "support/postgresql-releases.json")
    releases = _coverage.release_snapshot(snapshot, support)
    expected_core, expected_extensions = _coverage.expected_targets(support, releases)
    have_core, have_extensions = _coverage.inventory_targets(candidate)
    records = _coverage.verification_records(root, support)
    records.extend(candidate_verification_records(candidate, root, support))

    core_without_download = sorted(target for target in expected_core if target not in have_core)
    core_awaiting_verification = sorted(
        target for target in expected_core if target in have_core and not _coverage.verified(
            records, have_core[target], "postgresql", target[0], target[1], target[0], "current"))
    extension_without_download, extension_awaiting_verification = _coverage.classify_extension_targets(
        expected_extensions, have_extensions, records, have_core, support)
    missing_core = sorted(core_without_download + core_awaiting_verification)
    missing_extensions = sorted(extension_without_download + extension_awaiting_verification)
    outcomes = {
        outcome: [{"record": record["_record_file"],
                   "target": {"component": record["component"], "version": record["version"],
                              "postgresql_version": record["postgresql_version"],
                              "platform": record["platform"]},
                   "checks": record["test_cases"], "scope": record["scope"],
                   "profile_current": record["_profile_current"],
                   **({"reason": record["reason"]} if isinstance(record.get("reason"), str) else {})}
                  for record in records if record["outcome"] == outcome]
        for outcome in ("failed", "skipped")
    }
    return {
        "snapshot_as_of": snapshot["as_of"],
        "inventory_source": "unpublished-candidate",
        "publication_eligibility": "not-established-by-coverage",
        "required_core": len(expected_core),
        "missing_core": [list(target) for target in missing_core],
        "core_without_download": [list(target) for target in core_without_download],
        "core_awaiting_verification": [list(target) for target in core_awaiting_verification],
        "required_extension_targets": len(expected_extensions),
        "missing_extension": [list(target) for target in missing_extensions],
        "extension_without_download": [list(target) for target in extension_without_download],
        "extension_awaiting_verification": [list(target) for target in extension_awaiting_verification],
        "stale_verification_records": sum(record.get("_profile_current") is False for record in records),
        "verification_records_by_outcome": outcomes,
        "verification": "structural-only" if not missing_core and not missing_extensions else
        ("unverified" if not records else "incomplete"),
        "coverage_scope": "candidate target coverage only; staged archive bytes and publication eligibility are not established",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--candidate-inventory", required=True, type=Path,
                        help="unpublished structural-draft inventory")
    args = parser.parse_args(argv)
    try:
        result = report_candidate(args.root, args.candidate_inventory)
    except (OSError, UnicodeError, json.JSONDecodeError, _coverage.CoverageError,
            KeyError, TypeError, ValueError) as exc:
        print(f"candidate coverage: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    missing = result["missing_core"] or result["missing_extension"]
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
