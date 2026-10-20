#!/usr/bin/env python3
"""Write the selected Address Standardizer macOS core target."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("postgresql_version", choices=("17.11",))
    parser.add_argument("--architecture", required=True, choices=("arm64",))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import coverage
        import extension_archive_plan
        support = coverage.load_json(ROOT / "support.json")
        releases = coverage.load_json(ROOT / "support/postgresql-releases.json")
        extension_archive_plan.select_target(
            extension_archive_plan.plan(support, releases), "Address Standardizer",
            f"macos-{args.architecture}", args.postgresql_version, "3.7.0")
    except (coverage.CoverageError, ValueError, KeyError, TypeError) as exc:
        print(f"unsupported selected Address Standardizer macOS target: {exc}", file=sys.stderr)
        return 2
    finally:
        sys.path.remove(str(ROOT / "tools"))
    target = {
        "schema_version": 1,
        "profile_id": f"address-standardizer-publication-macos-{args.architecture}-{args.postgresql_version}",
        "postgresql_version": args.postgresql_version,
        "architecture": args.architecture,
        "platform": f"macos-{args.architecture}",
        "extension_version": "3.7.0",
        "core_archive": {"basename": f"postgresql-{args.postgresql_version}-macos-{args.architecture}.tar.gz"},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(target, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
