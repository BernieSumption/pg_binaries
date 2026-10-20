#!/usr/bin/env python3
"""Load an optional explicit unpublished macOS PostgreSQL core pin."""

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
PIN_DIR = ROOT / "support/macos-core-pins"
FIELDS = {"schema_version", "workflow", "run_id", "artifact_name", "archive_name", "sha256"}


class MissingPin(FileNotFoundError):
    pass


def load_pin(version, architecture, path=None):
    support = json.loads((ROOT / "support.json").read_text(encoding="utf-8"))
    releases = json.loads((ROOT / "support/postgresql-releases.json").read_text(encoding="utf-8"))
    supported_versions = {item["version"] for item in releases["releases"]}
    if (version not in supported_versions or architecture not in support["platform_architectures"]["macos"]):
        raise ValueError("unsupported macOS PostgreSQL version or architecture")
    path = Path(path) if path is not None else PIN_DIR / f"{version}-{architecture}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MissingPin(f"no macOS core pin for {version} {architecture}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid macOS core pin: {path}") from exc
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("macOS core pin has missing or unexpected fields")
    expected_archive = f"postgresql-{version}-macos-{architecture}.tar.gz"
    workflow = value["workflow"]
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1
            or not isinstance(workflow, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", workflow)
            or not isinstance(value["run_id"], int) or isinstance(value["run_id"], bool) or value["run_id"] <= 0
            or not isinstance(value["artifact_name"], str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", value["artifact_name"])
            or value["archive_name"] != expected_archive
            or not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])):
        raise ValueError("macOS core pin does not match the requested target or field formats")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("architecture")
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()
    pin = load_pin(args.version, args.architecture, args.path)
    for key in ("workflow", "run_id", "artifact_name", "archive_name", "sha256"):
        print(f"{key}={pin[key]}")


if __name__ == "__main__":
    try:
        main()
    except MissingPin as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
