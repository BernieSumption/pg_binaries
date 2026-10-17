#!/usr/bin/env python3
"""Summarize declared extension target tuples as unverified archive candidates."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys

_COVERAGE_SPEC = importlib.util.spec_from_file_location(
    "extension_plan_coverage", Path(__file__).with_name("coverage.py"))
_coverage = importlib.util.module_from_spec(_COVERAGE_SPEC)
_COVERAGE_SPEC.loader.exec_module(_coverage)


def plan(support, snapshot):
    """Group the exact declared SQL extension targets without inferring support."""
    _coverage.validate_support(support)
    releases = _coverage.release_snapshot(snapshot, support)
    _, targets = _coverage.expected_targets(support, releases)
    grouped = {}
    for project, extension in support["extensions"].items():
        for version in extension["versions"]:
            for platform in sorted({target[3] for target in targets
                                    if target[0] in extension["sql_names"] and target[1] == version}):
                by_major = {}
                for name, target_version, pg, target_platform in targets:
                    if (name in extension["sql_names"] and target_version == version
                            and target_platform == platform):
                        major = _coverage.version_parts(pg, "target")[0]
                        by_major.setdefault(major, set()).add((name, pg))
                for major, major_targets in by_major.items():
                    pg_versions = sorted({pg for _, pg in major_targets},
                                         key=lambda item: _coverage.version_parts(item, "target"))
                    if len(pg_versions) != 1:
                        raise _coverage.CoverageError(
                            f"{project} {version}: selected PostgreSQL major {major} has multiple minors")
                    sql_names = [name for name in extension["sql_names"]
                                 if any(target_name == name for target_name, _ in major_targets)]
                    grouped[(project, version, platform, major)] = {
                        "project": project,
                        "selected_version": version,
                        "platform": platform,
                        "postgresql_major": major,
                        "postgresql_version": pg_versions[0],
                        "sql_names": sql_names,
                        "postgresql_endpoint_versions": {"from": pg_versions[0], "to": pg_versions[-1]},
                        "covered_postgresql_versions": pg_versions,
                        "covered_target_tuple_count": len(major_targets),
                        "os_endpoint_labels": ["minimum", "current"],
                        "status": "candidate-unverified",
                        "publication_eligibility": "not-established",
                    }
    return {
        "status": "candidate-plan-unverified",
        "source": "support.json plus support/postgresql-releases.json",
        "grouping": "project + selected extension version + PostgreSQL major + platform",
        "range_semantics": "legacy range fields have identical endpoints for the one selected PostgreSQL minor",
        "candidate_archives": [grouped[key] for key in sorted(grouped)],
        "limitations": [
            "No build, archive, runtime, verification-record, or publication-eligibility claim is made.",
            "OS endpoint labels follow declared verification endpoint names; the plan contains no passing evidence.",
            "Known PostgreSQL and operating-system restrictions are applied from support.json before grouping.",
            "PostgreSQL major boundaries are kept separate because extension binaries generally target a major-version ABI.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="write JSON here; stdout is used when omitted")
    args = parser.parse_args(argv)
    try:
        result = plan(_coverage.load_json(args.root / "support.json"),
                      _coverage.load_json(args.root / "support" / "postgresql-releases.json"))
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (_coverage.CoverageError, OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"extension archive plan: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
