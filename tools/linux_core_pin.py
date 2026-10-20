#!/usr/bin/env python3
"""Load an optional exact unpublished Linux PostgreSQL core pin."""

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
PIN_DIR = ROOT / "support/linux-core-pins"
FIELDS = {"schema_version", "workflow", "run_id", "artifact_name", "archive_name", "sha256"}


class MissingPin(FileNotFoundError):
    pass


def load_pin(version, architecture, path=None):
    support = json.loads((ROOT / "support.json").read_text(encoding="utf-8"))
    releases = json.loads((ROOT / "support/postgresql-releases.json").read_text(encoding="utf-8"))
    supported_versions = {item["version"] for item in releases["releases"]}
    if (version not in supported_versions
            or architecture not in support["platform_architectures"]["linux"]):
        raise ValueError("unsupported Linux PostgreSQL version or architecture")
    path = Path(path) if path is not None else PIN_DIR / f"{version}-{architecture}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MissingPin(f"no Linux core pin for {version} {architecture}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Linux core pin: {path}") from exc
    expected_archive = f"postgresql-{version}-linux-{architecture}.tar.gz"
    if (not isinstance(value, dict) or set(value) != FIELDS
            or type(value.get("schema_version")) is not int or value["schema_version"] != 1
            or not isinstance(value.get("workflow"), str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", value["workflow"])
            or type(value.get("run_id")) is not int or value["run_id"] <= 0
            or not isinstance(value.get("artifact_name"), str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", value["artifact_name"])
            or value.get("archive_name") != expected_archive
            or not isinstance(value.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])):
        raise ValueError("Linux core pin does not match the requested target or field formats")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("architecture")
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()
    print(json.dumps(load_pin(args.version, args.architecture, args.path), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except MissingPin as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
