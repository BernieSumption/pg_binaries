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
        elif any(not coverage.verified(records, download, "postgresql", version,
                                      platform, version, endpoint)
                 for endpoint in ("minimum", "current")):
            core_verify.append(target)

    ext_without, ext_awaiting = coverage.classify_extension_targets(
        required_extensions, available_extensions, records)
    result = {
        "snapshot_as_of": snapshot["as_of"],
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
    """Select one declared PostgreSQL 15 through 18 Linux pilot build."""
    if not re.fullmatch(r"(15|16|17|18)\.[0-9]+", version):
        raise coverage.CoverageError(
            "Linux pilot currently supports PostgreSQL 15 through 18 minors only")
    if architecture not in ("x86_64", "arm64"):
        raise coverage.CoverageError("Linux pilot architecture must be x86_64 or arm64")
    work = plan(root)
    target = [version, f"linux-{architecture}"]
    if target not in work["build_missing"]["core"]:
        raise coverage.CoverageError(f"{target} is not a missing declared core build")
    return {"postgresql_version": version, "platform": target[1],
            "work": "build_missing", "snapshot_as_of": work["snapshot_as_of"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--select-linux-pilot", metavar="VERSION")
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), default="x86_64")
    args = parser.parse_args()
    try:
        result = (select_linux_pilot(args.root, args.select_linux_pilot, args.architecture)
                  if args.select_linux_pilot else plan(args.root))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (coverage.CoverageError, KeyError, TypeError, ValueError) as exc:
        print(f"plan-work: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
