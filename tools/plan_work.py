#!/usr/bin/env python3
"""Plan missing builds and verification from the current support snapshot.

This reports target-level work only. It does not dispatch CI or claim that
artifacts can be reused across targets beyond inventory ranges already
accepted by coverage.py.
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


def _load_coverage():
    spec = importlib.util.spec_from_file_location(
        "coverage", Path(__file__).with_name("coverage.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coverage = _load_coverage()


def plan(root):
    """Return deterministic target work derived from coverage inputs."""
    root = Path(root)
    support = coverage.load_json(root / "support.json")
    coverage.validate_support(support)
    coverage.validate_extension_policy(root, support)
    snapshot = coverage.load_json(root / "support" / "postgresql-releases.json")
    inventory = coverage.load_json(root / "inventory.json", required=False) or {
        "postgresql": {}, "extensions": {}}
    releases = coverage.release_snapshot(snapshot, support)
    required_core, required_extensions = coverage.expected_targets(support, releases)
    available_core, available_extensions = coverage.inventory_targets(inventory)
    records = coverage.verification_records(root, support)

    core_build, core_verify = [], []
    for version, platform in sorted(required_core):
        target = [version, platform]
        download = available_core.get((version, platform))
        if download is None:
            core_build.append(target)
        elif not coverage.verified(records, download, "postgresql", version,
                                   platform, version, "current"):
            core_verify.append(target)

    ext_without, ext_awaiting = coverage.classify_extension_targets(
        required_extensions, available_extensions, records, available_core, support)
    result = {
        "snapshot_as_of": snapshot["as_of"],
        "stale_verification_records": sum(r.get("_profile_current") is False for r in records),
        "build_missing": {
            "core": [list(target) for target in core_build],
            "extensions": [list(target) for target in ext_without],
        },
        "verify_downloaded": {
            "core": [list(target) for target in core_verify],
            "extensions": [list(target) for target in ext_awaiting],
        },
        "scope": "target-level planning from public inventory and verification records",
    }
    return result


def select_linux_pilot(root, version, architecture="x86_64"):
    """Select one declared Linux PostgreSQL pilot build."""
    if not re.fullmatch(r"[0-9]+\.[0-9]+", version) or int(version.split(".", 1)[0]) < 15:
        raise coverage.CoverageError(
            "Linux pilot requires a PostgreSQL major of at least 15")
    if architecture not in ("x86_64", "arm64"):
        raise coverage.CoverageError("Linux pilot architecture must be x86_64 or arm64")
    work = plan(root)
    target = [version, f"linux-{architecture}"]
    if target not in work["build_missing"]["core"]:
        raise coverage.CoverageError(f"{target} is not a missing declared core build")
    return {"postgresql_version": version, "platform": target[1],
            "work": "build_missing", "snapshot_as_of": work["snapshot_as_of"]}


def select_next_linux_pilot(root, architecture="x86_64"):
    """Select the highest missing target not already covered by current pilot evidence."""
    if architecture not in ("x86_64", "arm64"):
        raise coverage.CoverageError("Linux pilot architecture must be x86_64 or arm64")
    work = plan(root)
    platform = f"linux-{architecture}"
    support = coverage.load_json(Path(root) / "support.json")
    records = coverage.verification_records(Path(root), support)
    candidates = [target[0] for target in work["build_missing"]["core"]
                  if target[1] == platform]
    candidates = [version for version in candidates
                  if not _has_current_pilot_record(records, version, platform)]
    if not candidates:
        raise coverage.CoverageError(f"no missing declared core build for {platform}")
    version = max(candidates, key=lambda item: coverage.version_parts(item, "PostgreSQL version"))
    return {"postgresql_version": version, "platform": platform,
            "work": "build_missing", "snapshot_as_of": work["snapshot_as_of"]}


def select_pilot(root, version, platform):
    """Select one missing core target declared by the support snapshot."""
    work = plan(root)
    target = [version, platform]
    if target not in work["build_missing"]["core"]:
        raise coverage.CoverageError(f"{target} is not a missing declared core build")
    return {"postgresql_version": version, "platform": platform,
            "work": "build_missing", "snapshot_as_of": work["snapshot_as_of"]}


def select_next_pilot(root, platform):
    """Select the highest missing core target without reusable pilot evidence."""
    work = plan(root)
    support = coverage.load_json(Path(root) / "support.json")
    declared_platforms = {f"{os_name}-{architecture}"
                          for os_name, architectures in support["platform_architectures"].items()
                          for architecture in architectures}
    if platform not in declared_platforms:
        raise coverage.CoverageError(f"undeclared pilot platform: {platform}")
    records = coverage.verification_records(Path(root), support)
    candidates = [version for version, candidate_platform in work["build_missing"]["core"]
                  if candidate_platform == platform]
    candidates = [version for version in candidates
                  if not _has_current_pilot_record(records, version, platform)]
    if not candidates:
        raise coverage.CoverageError(f"no missing declared core build for {platform}")
    version = max(candidates, key=lambda item: coverage.version_parts(item, "PostgreSQL version"))
    return {"postgresql_version": version, "platform": platform,
            "work": "build_missing", "snapshot_as_of": work["snapshot_as_of"]}


def _has_current_pilot_record(records, version, platform):
    return any(record.get("scope") == "pilot-smoke"
               and record.get("_profile_current") is True
               and record.get("outcome") == "passed"
               and record.get("component") == "postgresql"
               and record.get("version") == version
               and record.get("postgresql_version") == version
               and record.get("platform") == platform
               and record.get("environment", {}).get("endpoint") == "current"
               for record in records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--select-linux-pilot", metavar="VERSION")
    parser.add_argument("--select-next-linux-pilot", action="store_true")
    parser.add_argument("--select-pilot", metavar="VERSION")
    parser.add_argument("--select-next-pilot", action="store_true")
    parser.add_argument("--platform", help="declared OS and architecture, for a generic pilot selector")
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), default="x86_64")
    args = parser.parse_args()
    try:
        selectors = (int(args.select_linux_pilot is not None)
                     + int(args.select_next_linux_pilot)
                     + int(args.select_pilot is not None)
                     + int(args.select_next_pilot))
        if selectors > 1:
            raise coverage.CoverageError("choose only one pilot selector")
        if args.select_linux_pilot is not None:
            result = select_linux_pilot(args.root, args.select_linux_pilot, args.architecture)
        elif args.select_next_linux_pilot:
            result = select_next_linux_pilot(args.root, args.architecture)
        elif args.select_pilot is not None:
            if not args.platform:
                raise coverage.CoverageError("--platform is required for generic pilot selection")
            result = select_pilot(args.root, args.select_pilot, args.platform)
        elif args.select_next_pilot:
            if not args.platform:
                raise coverage.CoverageError("--platform is required for generic pilot selection")
            result = select_next_pilot(args.root, args.platform)
        else:
            result = plan(args.root)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (coverage.CoverageError, KeyError, TypeError, ValueError) as exc:
        print(f"plan-work: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
