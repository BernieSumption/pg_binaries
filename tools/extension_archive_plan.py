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
                        "covered_target_tuple_count": len(major_targets),
                        "status": "candidate-unverified",
                        "publication_eligibility": "not-established",
                    }
    return {
        "status": "candidate-plan-unverified",
        "source": "support.json plus support/postgresql-releases.json",
        "grouping": "project + selected extension version + PostgreSQL major + platform",
        "target_semantics": "each candidate archive targets one selected PostgreSQL minor and platform",
        "candidate_archives": [grouped[key] for key in sorted(grouped)],
        "limitations": [
            "No build, archive, runtime, verification-record, or publication-eligibility claim is made.",
            "Known PostgreSQL and operating-system restrictions are applied from support.json before grouping.",
            "PostgreSQL major boundaries are kept separate because extension binaries generally target a major-version ABI.",
        ],
    }


def select_target(result, project, platform, postgresql_version, extension_version=None):
    matches = [item for item in result["candidate_archives"]
               if item["project"] == project and item["platform"] == platform
               and item["postgresql_version"] == postgresql_version
               and (extension_version is None or item["selected_version"] == extension_version)]
    if len(matches) != 1:
        raise ValueError(f"expected one selected target for {project}, {platform}, "
                         f"PostgreSQL {postgresql_version}, extension version "
                         f"{extension_version or 'unspecified'}; found {len(matches)}")
    return matches[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="write JSON here; stdout is used when omitted")
    parser.add_argument("--project", help="select one declared extension project")
    parser.add_argument("--platform", help="select one declared OS and architecture")
    parser.add_argument("--postgresql-version", help="select one exact PostgreSQL release")
    parser.add_argument("--extension-version", help="disambiguate selected extension releases")
    parser.add_argument("--github-output", type=Path,
                        help="append selected target fields to a GitHub Actions output file")
    args = parser.parse_args(argv)
    try:
        result = plan(_coverage.load_json(args.root / "support.json"),
                      _coverage.load_json(args.root / "support" / "postgresql-releases.json"))
        selection = (args.project, args.platform, args.postgresql_version)
        if args.extension_version and not all(selection):
            raise ValueError("extension-version requires project, platform and postgresql-version")
        if any(selection):
            if not all(selection):
                raise ValueError("project, platform and postgresql-version must be selected together")
            result = select_target(result, *selection, args.extension_version)
        if args.github_output:
            if not all(selection):
                raise ValueError("github-output requires an exact selected target")
            with args.github_output.open("a", encoding="utf-8") as stream:
                for key in ("project", "selected_version", "platform", "postgresql_version",
                            "postgresql_major"):
                    stream.write(f"{key}={result[key]}\n")
                stream.write(f"sql_names={json.dumps(result['sql_names'], separators=(',', ':'))}\n")
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
