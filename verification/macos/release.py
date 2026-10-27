#!/usr/bin/env python3
"""Verify PostgreSQL and selected macOS extension archives in combinations."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from verification.macos.runtime import verify
from verification.archive import read_archive
from verification.records import RecordError, selected_inputs


TARGET = "macos-arm64"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as archive:
        for chunk in iter(lambda: archive.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()


def builtin_controls(archive: Path) -> list[str]:
    prefix = "postgresql/share/extension/"
    entries = read_archive(archive)
    return sorted(path.removeprefix(prefix).removesuffix(".control")
                  for path, entry in entries.items()
                  if path.startswith(prefix) and path.endswith(".control")
                  and "/" not in path[len(prefix):] and entry.kind == "file")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("postgresql_archive", type=Path)
    parser.add_argument("output", type=Path, help="directory for report and per-combination logs")
    parser.add_argument("--target", choices=("macos-arm64", "macos-x86_64"), default=TARGET)
    parser.add_argument("--package-archive", action="append", default=[], metavar="PACKAGE=PATH",
                        help="selected package archive; repeat once for each package")
    parser.add_argument("--build-record", action="append", default=[], metavar="COMPONENT=PATH",
                        help="build record for PostgreSQL or a selected package; repeat for each")
    parser.add_argument("--origin-run", action="append", default=[], metavar="COMPONENT=RUN_ID",
                        help="workflow run that produced a selected archive; repeat for each component")
    arguments = parser.parse_args()
    target = arguments.target
    required_arch = target.removeprefix("macos-")
    if platform.system() != "Darwin" or platform.machine() != required_arch:
        parser.error(f"{target} verification must run on a macOS {required_arch} host")

    support = json.loads((ROOT / "support.json").read_text(encoding="utf-8"))
    expected = set(support["packages"])

    packages: dict[str, Path] = {}
    for item in arguments.package_archive:
        name, separator, filename = item.partition("=")
        if not separator or name not in expected or not filename or name in packages:
            parser.error(f"invalid or duplicate --package-archive value: {item!r}")
        packages[name] = Path(filename)
    if set(packages) != expected:
        parser.error(f"package archives do not match support.json: missing={sorted(expected - set(packages))}")
    packages = {name: packages[name] for name in support["packages"]}

    archives = {"postgresql": arguments.postgresql_archive, **packages}
    missing = [f"{name}: {path}" for name, path in archives.items() if not path.is_file()]
    if missing:
        parser.error("missing archive file(s): " + "; ".join(missing))
    record_paths: dict[str, Path] = {}
    for item in arguments.build_record:
        name, separator, filename = item.partition("=")
        if not separator or name not in archives or not filename or name in record_paths:
            parser.error(f"invalid or duplicate --build-record value: {item!r}")
        record_paths[name] = Path(filename)
    if set(record_paths) != set(archives):
        parser.error(f"build records do not match selected archives: missing={sorted(set(archives) - set(record_paths))}")
    origin_runs: dict[str, int] = {}
    for item in arguments.origin_run:
        name, separator, run_id = item.partition("=")
        if not separator or name not in archives or not run_id.isdecimal() or name in origin_runs:
            parser.error(f"invalid or duplicate --origin-run value: {item!r}")
        origin_runs[name] = int(run_id)
        if origin_runs[name] <= 0:
            parser.error(f"workflow run ID must be positive: {item!r}")
    if origin_runs and set(origin_runs) != set(archives):
        parser.error(f"origin runs do not match selected archives: missing={sorted(set(archives) - set(origin_runs))}")
    archive_hashes = {name: sha256(path) for name, path in archives.items()}
    records: dict[str, dict] = {}
    for name, path in record_paths.items():
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            parser.error(f"cannot read {name} build record: {error}")
        if not isinstance(record, dict) or not isinstance(record.get("archive"), dict):
            parser.error(f"invalid {name} build record structure")
        if (record.get("schema_version") != 1
                or not isinstance(record.get("git_revision"), str)
                or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", record["git_revision"])):
            parser.error(f"{name} build record lacks a valid schema version or Git revision")
        if name != "postgresql" and not isinstance(record.get("postgresql_archive"), dict):
            parser.error(f"{name} build record lacks its PostgreSQL archive")
        if (record.get("component") != name or record.get("target") != target
                or record.get("archive", {}).get("sha256") != archive_hashes[name]
                or record.get("archive", {}).get("filename") != archives[name].name):
            parser.error(f"{name} build record does not identify its selected archive")
        if name != "postgresql" and record.get("postgresql_archive", {}).get("sha256") != archive_hashes["postgresql"]:
            parser.error(f"{name} was built against a different PostgreSQL archive")
        try:
            sources, build_inputs = selected_inputs(support, target, name)
        except RecordError as error:
            parser.error(str(error))
        if record.get("sources") != sources or record.get("build_inputs") != build_inputs:
            parser.error(f"{name} build record uses different selected sources or build inputs")
        records[name] = record
    if arguments.output.exists():
        parser.error(f"output directory already exists: {arguments.output}")
    arguments.output.mkdir(parents=True)

    report = {
        "schema_version": 1,
        "target": target,
        "macos_version": platform.mac_ver()[0] or platform.release(),
        "verification_git_revision": git_revision(),
        "archives": {
            name: {"filename": path.name, "sha256": archive_hashes[name],
                   "build_record": record_paths[name].name,
                   "origin_run": origin_runs.get(name)}
            for name, path in archives.items()
        },
        "build_records": {name: record for name, record in records.items()},
        "postgresql_builtin_extensions": [],
        "combinations": [],
    }

    combinations = [(name, {name: path}) for name, path in packages.items()]
    combinations.append(("postgresql-only", {}))
    combinations.append(("all-packages", packages))
    for index, (label, selected) in enumerate(combinations, start=1):
        log = arguments.output / f"{index:02d}-{label}.log"
        entry = {"name": label, "outcome": "passed", "reason": None, "log": log.name, "checks": []}
        try:
            checks = verify(arguments.postgresql_archive, selected, arguments.output / f"{index:02d}-{label}", target)
            entry["checks"] = checks
            failed = [item for item in checks if item["outcome"] in ("failed", "not_run")]
            if failed:
                entry["outcome"] = "failed"
                entry["reason"] = f"{len(failed)} required check(s) failed or could not run"
            log.write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
        except Exception as error:
            entry["outcome"] = "failed"
            entry["reason"] = str(error)
            log.write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")
        report["combinations"].append(entry)

    postgresql_only = next(item for item in report["combinations"] if item["name"] == "postgresql-only")
    if postgresql_only["outcome"] == "passed":
        try:
            report["postgresql_builtin_extensions"] = builtin_controls(arguments.postgresql_archive)
        except Exception as error:
            postgresql_only["checks"].append({"name": "built-in inventory", "outcome": "failed",
                                               "reason": str(error)})
            postgresql_only["outcome"] = "failed"
            postgresql_only["reason"] = "could not read built-in controls from PostgreSQL archive"

    report_path = arguments.output / "verification-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report_path)
    return 1 if any(item["outcome"] != "passed" for item in report["combinations"]) else 0


if __name__ == "__main__":
    sys.exit(main())
