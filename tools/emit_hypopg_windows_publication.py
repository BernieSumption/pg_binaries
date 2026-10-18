#!/usr/bin/env python3
"""Emit checksum-bound publication records for hypopg on Windows x86-64."""

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile

import coverage
from hypopg_windows_symbols import verify_symbols
from windows_core_pin import PG_VERSIONS, load_identity

PROFILE_ID = "hypopg-publication-windows-x86_64-18.6"
PG_VERSION = "18.6"
HYPOPG_VERSION = "1.4.3"
ARCHITECTURE = "x86_64"
PLATFORM = "windows-x86_64"
_CORE = load_identity()
CORE_SHA256 = _CORE["sha256"]
CORE_BUILD_ID = _CORE["build_id"]
CORE_SOURCE_REVISION = _CORE["source_revision"]
CORE_STATUS = _CORE["status"]
SOURCE_URL = "https://github.com/HypoPG/hypopg/archive/refs/tags/1.4.3.tar.gz"
SOURCE_SHA256 = "498a961d88cf37057fd9e98027d06fe805c8959d51895c3d9b94c9eb4e14f706"
CASES = {"archive-suite", "static-analysis"}


@dataclass(frozen=True)
class Target:
    PG_VERSION: str
    PROFILE_ID: str
    CORE_SHA256: str
    CORE_BUILD_ID: str
    CORE_SOURCE_REVISION: str
    CORE_STATUS: str


def load_target(pg_version):
    core = load_identity(pg_version=pg_version)
    return Target(pg_version, f"hypopg-publication-windows-x86_64-{pg_version}",
                  core["sha256"], core["build_id"], core["source_revision"], core["status"])


def _fail(message):
    raise coverage.CoverageError(message)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sidecar(path, digest):
    try:
        lines = Path(str(path) + ".sha256").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _fail(f"missing checksum sidecar for {Path(path).name}")
    name = Path(path).name
    if (len(lines) != 1 or not re.fullmatch(rf"[0-9a-fA-F]{{64}}\s+\*?{re.escape(name)}", lines[0])
            or lines[0].split()[0].lower() != digest):
        _fail(f"checksum sidecar does not match {name}")


def _json(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _fail(f"{label} report is missing or invalid")
    if not isinstance(value, dict):
        _fail(f"{label} report must be a JSON object")
    return value


def _metadata(path, target=None):
    target = sys.modules[__name__] if target is None else target
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            item = next((m for m in members if m.name == "metadata.json" and m.isfile()
                         and m.size <= 1024 * 1024), None)
            if item is None:
                _fail("hypopg archive requires bounded metadata.json")
            value = json.loads(archive.extractfile(item).read().decode("utf-8"))
            names = {m.name for m in members}
            if len(names) != len(members):
                _fail("hypopg archive contains duplicate paths")
            for member in members:
                path_name = Path(member.name)
                if path_name.is_absolute() or ".." in path_name.parts or member.issym() or member.islnk():
                    _fail("hypopg archive contains an unsafe path or link")
                if member.isfile() and Path(member.name).suffix.lower() in {".exe", ".so", ".dylib"}:
                    _fail("Windows hypopg archive contains unexpected native code")
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot inspect hypopg archive: {exc}")
    expected = {
        "project": "hypopg", "version": HYPOPG_VERSION, "sql_names": ["hypopg"],
        "postgresql_version": target.PG_VERSION, "platform": "windows", "architecture": ARCHITECTURE,
        "source": {"url": SOURCE_URL, "sha256": SOURCE_SHA256},
        "core_archive": {"basename": f"postgresql-{target.PG_VERSION}-{PLATFORM}.tar.gz",
                         "sha256": target.CORE_SHA256},
        "release_eligible": False, "core_status": target.CORE_STATUS,
    }
    if not isinstance(value, dict) or any(value.get(k) != v for k, v in expected.items()):
        _fail("hypopg metadata does not match the pinned publication target")


def _step(value, name):
    mapping = {"success": "passed", "failure": "failed", "skipped": "skipped",
               "cancelled": "skipped", "timed_out": "failed"}
    if value not in mapping:
        _fail(f"{name} result must be a GitHub Actions step outcome")
    return mapping[value]


def emit(root, core_dir, archives, output, step_results, os_version, image_id, environ=None, target=None):
    target = sys.modules[__name__] if target is None else target
    root, core_dir, archives, output = map(Path, (root, core_dir, archives, output))
    environ = os.environ if environ is None else environ
    if not isinstance(step_results, dict) or set(step_results) != CASES:
        _fail("step_results must identify archive-suite and static-analysis")
    results = {case: _step(step_results[case], case) for case in sorted(CASES)}
    revision, run_id = environ.get("GITHUB_SHA", ""), environ.get("GITHUB_RUN_ID", "")
    repository, server_url = environ.get("GITHUB_REPOSITORY", ""), environ.get("GITHUB_SERVER_URL", "")
    if not coverage.REVISION.fullmatch(revision) or not run_id.isdigit() or not repository or not server_url:
        _fail("GitHub Actions revision and run provenance are required")
    if not re.fullmatch(r"\d+(?:\.\d+)*", os_version or "") or not image_id:
        _fail("Windows runner version and image identifier are required")
    profile = coverage.verification_profile(root, target.PROFILE_ID)
    if (profile["scope"] != "publication" or profile["platforms"] != [PLATFORM]
            or profile["case_ids"] != sorted(CASES) or not profile["sources_available"]):
        _fail("registered profile does not match this hypopg publication suite")
    core_name = f"postgresql-{target.PG_VERSION}-{PLATFORM}.tar.gz"
    extension_name = f"hypopg-{HYPOPG_VERSION}-postgresql-{target.PG_VERSION}-{PLATFORM}.tar.gz"
    core_archive, extension_archive = core_dir / core_name, archives / extension_name
    publication = output / "publication"
    publication.mkdir(parents=True, exist_ok=True)
    attempt_path = publication / "attempt.json"
    attempt = {
        "schema_version": 1, "run_id": run_id, "source_revision": revision,
        "profile_id": target.PROFILE_ID, "postgresql_version": target.PG_VERSION, "hypopg_version": HYPOPG_VERSION,
        "architecture": ARCHITECTURE, "steps": {c: step_results[c] for c in sorted(CASES)},
        "release_eligible": False, "core_status": target.CORE_STATUS,
        "archives_present": {core_name: core_archive.is_file(), extension_name: extension_archive.is_file()},
    }
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not core_archive.is_file() or not extension_archive.is_file():
        return [attempt_path]
    digests = {core_name: sha256_file(core_archive), extension_name: sha256_file(extension_archive)}
    for archive in (core_archive, extension_archive):
        _sidecar(archive, digests[archive.name])
    if digests[core_name] != target.CORE_SHA256:
        _fail("PostgreSQL core archive does not match the selected successful Windows build")
    _metadata(extension_archive, target)
    attempt["archives"] = digests
    attempt_path.write_text(json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    static_path, probe_path = output / "static-analysis.json", output / "probe-output.txt"
    reports = {name: sha256_file(path) for name, path in
               (("static_analysis", static_path), ("probe_output", probe_path),
                ("pe_dependency_analysis", output / "pe-dependency-analysis.json")) if path.is_file()}
    if results["archive-suite"] == "passed":
        if not probe_path.is_file():
            _fail("archive suite did not retain its hypopg output")
        if "Index Scan using" not in probe_path.read_text(encoding="utf-8"):
            _fail("archive suite output does not show the hypothetical index plan")
    symbols = None
    if results["static-analysis"] == "passed":
        symbols = verify_symbols(extension_archive, output / "hypopg.pdb")
        static = _json(static_path, "static analysis")
        if (static.get("symbols") != symbols or static.get("passed") is not True or static.get("architecture") != ARCHITECTURE
                or static.get("archives") != digests or not static.get("inspected_files")
                or static.get("native_extension_files") != ["hypopg/lib/hypopg.dll"]
                or static.get("pe_dependency_analysis_sha256") != reports.get("pe_dependency_analysis")):
            _fail("static analysis did not bind the retained PE dependency report")
        pe = _json(output / "pe-dependency-analysis.json", "PE dependency analysis")
        if (pe.get("outcome") != "passed" or
                {item.get("basename"): item.get("sha256") for item in pe.get("archives", [])
                 if isinstance(item, dict)} != digests or
                "lib/hypopg.dll" not in pe.get("inspected_files", [])):
            _fail("static analysis did not pass over the exact final archives")
    ci = {"provider": "github-actions", "run_id": run_id,
          "run_url": f"{server_url.rstrip('/')}/{repository}/actions/runs/{run_id}",
          "source_revision": revision, "build_revision": revision, "test_revision": revision}
    outcome = "failed" if "failed" in results.values() else "skipped" if "skipped" in results.values() else "passed"
    receipt = {
        "schema_version": 1, "profile_id": target.PROFILE_ID, "profile_revision": profile["profile_revision"],
        "test_revision": revision, "project": "HypoPG", "version": HYPOPG_VERSION,
        "postgresql_version": target.PG_VERSION, "architecture": ARCHITECTURE, "platform": PLATFORM,
        "endpoint": "current", "case_results": results, "archives": digests,
        "symbols": symbols, "extension_archive": extension_name, "reports": reports, "clean_system": True,
        "dependency_check_profile": "windows-pe-archive-relocation-v1",
        "dependency_checks_passed": results["static-analysis"] == "passed",
        "release_eligible": False, "core_status": target.CORE_STATUS,
        "environment": {"os": "windows", "os_version": os_version, "architecture": ARCHITECTURE,
                        "image_id": image_id},
        "ci": ci,
    }
    receipt_path = publication / "current-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = {
        "schema_version": 2, "scope": "publication", "profile_id": target.PROFILE_ID,
        "profile_revision": profile["profile_revision"], "test_cases": profile["case_ids"],
        "case_results": results, "test_revision": revision, "ci": ci, "outcome": outcome,
        "sha256": digests[extension_name], "component": "hypopg", "project": "HypoPG",
        "version": HYPOPG_VERSION, "platform": PLATFORM, "postgresql_version": target.PG_VERSION,
        "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": target.PG_VERSION},
        "prerequisite_archives": [],
        "release_eligible": False, "core_status": target.CORE_STATUS,
        "environment": {"os": "windows", "os_version": os_version, "architecture": ARCHITECTURE,
                        "clean_system": True, "endpoint": "current", "image_id": image_id,
                        "dependency_check_profile": receipt["dependency_check_profile"],
                        "dependency_checks_passed": receipt["dependency_checks_passed"]},
    }
    coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
    records = publication / "records"
    records.mkdir(parents=True, exist_ok=True)
    path = records / f"hypopg-{HYPOPG_VERSION}-postgresql-{target.PG_VERSION}-{PLATFORM}-current-{run_id}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return [attempt_path, receipt_path, path]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgresql-version", choices=PG_VERSIONS, default="18.6")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-archives", type=Path, required=True)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--os-version", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--archive-suite-result", required=True)
    parser.add_argument("--static-analysis-result", required=True)
    args = parser.parse_args()
    try:
        for path in emit(args.root, args.core_archives, args.archives, args.output,
                         {"archive-suite": args.archive_suite_result,
                          "static-analysis": args.static_analysis_result},
                         args.os_version, args.image_id, target=load_target(args.postgresql_version)):
            print(path)
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"hypopg Windows publication evidence: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
