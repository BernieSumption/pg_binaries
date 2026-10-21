#!/usr/bin/env python3
"""Validate and retain one selected PostGIS macOS publication run."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
from urllib.parse import unquote

import coverage
import license_pointer


PG_VERSIONS = {"15.19", "16.15", "17.11", "18.6"}
EXTENSION_VERSION = "3.6.4"
TARGETS = Path(__file__).resolve().parent / "postgis_macos_targets"
SQL_NAMES = ["postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology"]
CASES = ["archive-suite", "static-analysis"]
MAX_EVIDENCE_BYTES = 1024 * 1024


def _read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_EVIDENCE_BYTES:
        raise coverage.CoverageError(f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"invalid evidence JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"evidence JSON must be an object: {path}")
    return value


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar(path, digest):
    sidecar = Path(f"{path}.sha256")
    if sidecar.is_symlink() or not sidecar.is_file():
        raise coverage.CoverageError(f"missing checksum sidecar for {Path(path).name}")
    lines = sidecar.read_text(encoding="utf-8").splitlines()
    if lines != [f"{digest}  {Path(path).name}"]:
        raise coverage.CoverageError(f"checksum sidecar does not match {Path(path).name}")


def _retain(source, destination):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_EVIDENCE_BYTES:
        raise coverage.CoverageError(f"evidence must be a regular file of at most {MAX_EVIDENCE_BYTES} bytes: {source}")
    if destination.exists():
        if destination.is_symlink() or not destination.is_file() or destination.read_bytes() != source.read_bytes():
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _write_json(path, value):
    path = Path(path)
    serialized = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.is_symlink():
        raise coverage.CoverageError(f"refusing to replace symlink evidence {path}")
    if path.exists():
        if not path.is_file() or path.read_text(encoding="utf-8") != serialized:
            raise coverage.CoverageError(f"refusing to replace retained evidence {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")


def _metadata(archive, core_name, core_sha, architecture, pg_version):
    try:
        with tarfile.open(archive, "r:gz") as stream:
            members = stream.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                raise coverage.CoverageError("PostGIS archive contains duplicate paths")
            for member in members:
                path = Path(member.name)
                if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                    raise coverage.CoverageError("PostGIS archive contains an unsafe path or link")
            member = next((item for item in members if item.name == "metadata.json" and item.isfile()
                           and item.size <= MAX_EVIDENCE_BYTES), None)
            if member is None:
                raise coverage.CoverageError("PostGIS archive requires bounded metadata.json")
            metadata = json.loads(stream.extractfile(member).read().decode("utf-8"))
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"cannot inspect PostGIS archive: {exc}") from exc
    expected = {
        "project": "postgis", "version": EXTENSION_VERSION, "sql_names": SQL_NAMES,
        "postgresql_version": pg_version, "platform": "macos", "architecture": architecture,
        "core_archive": {"basename": core_name, "sha256": core_sha},
    }
    if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in expected.items()):
        raise coverage.CoverageError("PostGIS metadata does not bind the selected core and target")
    if not coverage.REVISION.fullmatch(str(metadata.get("source_revision", ""))) or not str(
            metadata.get("build_id", "")).startswith("github-"):
        raise coverage.CoverageError("PostGIS metadata lacks build provenance")
    return metadata


def _runner_image(path, architecture):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_EVIDENCE_BYTES:
        raise coverage.CoverageError("runner-image evidence must be a bounded regular file")
    text = path.read_text(encoding="utf-8")
    image_name = "macos-15-arm64" if architecture == "arm64" else "macos-15"
    image = re.search(rf"Image: ({re.escape(image_name)})\s*$", text, re.M)
    release = re.search(r"Image Release: https://github\.com/actions/runner-images/releases/tag/([^\s]+)", text)
    if not image or not release:
        raise coverage.CoverageError("runner-image evidence must identify the selected macOS image release")
    return f"{image.group(1)}/{unquote(release.group(1)).split('/', 1)[1]}"


def _profile_at_revision(root, revision, profile_id):
    def source(path):
        result = subprocess.run(
            ["git", "show", f"{revision}:{path}"], cwd=root, capture_output=True, check=False)
        if result.returncode:
            raise coverage.CoverageError(f"profile source {path} is absent at CI revision {revision}")
        return result.stdout

    registry = json.loads(source("support/verification-profiles.json"))
    historical = registry.get("profiles", {}).get(profile_id)
    if historical is None:
        raise coverage.CoverageError(f"verification profile {profile_id} was not registered at CI revision {revision}")
    declared = coverage.load_json(root / "support/verification-profiles.json")["profiles"][profile_id]
    if (any(historical.get(field) != declared.get(field)
            for field in ("scope", "platforms", "case_ids"))
            or not set(declared["sources"]).issubset(historical.get("sources", []))):
        raise coverage.CoverageError("verification profile cases or retained sources changed after the CI run")
    hashes = {}
    for path in historical["sources"]:
        hashes[path] = hashlib.sha256(source(path).replace(b"\r\n", b"\n")).hexdigest()
    old_revision = coverage.profile_revision(
        profile_id, historical["scope"], historical["case_ids"],
        historical["platforms"], hashes)
    current = coverage.verification_profile(root, profile_id)
    if old_revision not in current["compatible_profile_revisions"]:
        raise coverage.CoverageError("CI profile revision has no reviewed current equivalence")
    for path in declared["sources"]:
        if source(path).replace(b"\r\n", b"\n") != (root / path).read_bytes().replace(b"\r\n", b"\n"):
            raise coverage.CoverageError(f"profile source {path} changed after the CI run")


def import_run(root, build_artifact, verification_artifact, runner_image_evidence, run_id, target_path=None):
    root, build_artifact, verification_artifact = map(Path, (root, build_artifact, verification_artifact))
    run_id = str(run_id)
    if not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise coverage.CoverageError("run_id must be numeric")
    target_path = Path(target_path) if target_path else TARGETS / "18.6-arm64.json"
    target = _read_json(target_path)
    pg_version = target.get("postgresql_version")
    architecture = target.get("architecture")
    platform = target.get("platform")
    profile_id = target.get("profile_id")
    if (architecture not in {"arm64", "x86_64"} or platform != f"macos-{architecture}"
            or pg_version not in PG_VERSIONS
            or target.get("extension_version") != EXTENSION_VERSION
            or target.get("project") != "PostGIS"
            or target.get("schema_version") != 1
            or target.get("core_archive", {}).get("basename") != f"postgresql-{pg_version}-{platform}.tar.gz"
            or profile_id != f"postgis-publication-macos-{architecture}-{pg_version}"):
        raise coverage.CoverageError("selected PostGIS macOS target is invalid")
    profile = coverage.verification_profile(root, profile_id)
    if (profile["scope"] != "publication" or profile["platforms"] != [platform]
            or profile["case_ids"] != CASES):
        raise coverage.CoverageError("registered profile does not match selected PostGIS macOS publication")

    core_name = f"postgresql-{pg_version}-{platform}.tar.gz"
    extension_name = f"postgis-{EXTENSION_VERSION}-postgresql-{pg_version}-{platform}.tar.gz"
    core = build_artifact / "core" / core_name
    extension = build_artifact / "output" / extension_name
    if any(path.is_symlink() or not path.is_file() for path in (core, extension)):
        raise coverage.CoverageError("exact core and PostGIS archives are required")
    digests = {core_name: _sha256(core), extension_name: _sha256(extension)}
    for archive in (core, extension):
        _sidecar(archive, digests[archive.name])
    core_target = _read_json(build_artifact / "core" / "target.json")
    core_identity = core_target.get("core_archive", {})
    if (core_target.get("profile_id") != profile_id
            or core_identity.get("basename") != core_name
            or core_identity.get("sha256") != digests[core_name]):
        raise coverage.CoverageError("core target provenance does not match the downloaded core bytes")
    metadata = _metadata(extension, core_name, digests[core_name], architecture, pg_version)
    _profile_at_revision(root, metadata["source_revision"], profile_id)
    license_pointer.verify_archive(extension, "postgis")

    attempt = _read_json(verification_artifact / "publication/attempt.json")
    verifier = _read_json(verification_artifact / "publication/postgis-macos-verification.json")
    static = _read_json(verification_artifact / "static-analysis.json")
    if (str(attempt.get("run_id")) != run_id or attempt.get("source_revision") != metadata["source_revision"]
            or attempt.get("archives") != digests or attempt.get("steps", {}).get("archive-suite") != "success"
            or attempt.get("steps", {}).get("diagnostics") != "skipped"
            or attempt.get("steps", {}).get("symbols") != "skipped"):
        raise coverage.CoverageError("raw archive-bound attempt does not match exact archives and build revision")
    if (verifier.get("outcome") != "passed" or str(verifier.get("test_run_id")) != run_id
            or verifier.get("test_revision") != metadata["source_revision"]
            or verifier.get("archives") != digests or verifier.get("platform") != platform
            or verifier.get("architecture") != architecture
            or verifier.get("postgresql_version") != pg_version or verifier.get("version") != EXTENSION_VERSION):
        raise coverage.CoverageError("fresh-runner verifier record does not bind the selected run and archives")
    if (static.get("passed") is not True or static.get("findings")
            or static.get("architecture") != architecture):
        raise coverage.CoverageError("fresh-runner Mach-O analysis did not pass cleanly")
    static_archives = {item["basename"]: item["sha256"] for item in static.get("archives", [])}
    if static_archives != digests:
        raise coverage.CoverageError("Mach-O report does not bind the exact archive bytes")
    probe = verification_artifact / "probe-output.txt"
    raster = verification_artifact / "raster-probe.txt"
    if any(path.is_symlink() or not path.is_file() for path in (probe, raster)):
        raise coverage.CoverageError("SQL probe outputs must be regular files")
    probe_text, raster_text = probe.read_text(encoding="utf-8"), raster.read_text(encoding="utf-8")
    if (any(not re.search(rf"(?m)^\s*{re.escape(name)}\s*\|\s*3\.6\.4\s*$", probe_text)
            for name in SQL_NAMES)
            or not re.search(r"(?m)^SET\s*$", raster_text)
            or not re.search(r"(?m)^DO\s*$", raster_text)):
        raise coverage.CoverageError("retained SQL and raster probe outputs do not show all selected checks")
    os_version = re.fullmatch(
        rf"macOS-(\d+(?:\.\d+)+)-{re.escape(architecture)}(?:-.*)?",
        verifier["runner_os"])
    if not os_version:
        raise coverage.CoverageError("cannot extract macOS version from verifier runner identity")

    image_id = _runner_image(runner_image_evidence, architecture)
    ci = {
        "provider": "github-actions", "run_id": run_id,
        "run_url": f"https://github.com/BernieSumption/pg_binaries/actions/runs/{run_id}",
        "build_revision": metadata["source_revision"],
        "source_revision": metadata["source_revision"],
        "test_revision": verifier["test_revision"],
    }
    environment = {
        "os": "macos", "os_version": os_version.group(1), "architecture": architecture,
        "image_id": image_id, "endpoint": "current", "clean_system": True,
        "dependency_check_profile": "macho-system-dependencies-v1", "dependency_checks_passed": True,
    }
    results = {"archive-suite": "passed", "static-analysis": "passed"}
    reports = {
        "static_analysis": _sha256(verification_artifact / "static-analysis.json"),
        "postgis_verification": _sha256(verification_artifact / "publication/postgis-macos-verification.json"),
        "probe_output": _sha256(probe), "raster_probe": _sha256(raster),
    }
    receipt = {
        "schema_version": 1, "profile_id": profile_id,
        "profile_revision": profile["profile_revision"], "test_revision": verifier["test_revision"],
        "project": "PostGIS", "version": EXTENSION_VERSION, "postgresql_version": pg_version,
        "platform": platform, "architecture": architecture, "endpoint": "current",
        "case_results": results, "archives": digests, "extension_archive": extension_name,
        "core_target": core_target, "build_id": metadata["build_id"], "ci": ci,
        "environment": environment, "reports": reports,
    }
    records = []
    for component in SQL_NAMES:
        record = {
            "schema_version": 2, "scope": "publication", "profile_id": profile_id,
            "profile_revision": profile["profile_revision"], "test_cases": CASES,
            "case_results": results, "test_revision": verifier["test_revision"], "ci": ci,
            "outcome": "passed", "sha256": digests[extension_name], "component": component,
            "project": "PostGIS", "version": EXTENSION_VERSION, "platform": platform,
            "postgresql_version": pg_version,
            "assembled_core": {"archive": core_name, "sha256": digests[core_name], "version": pg_version},
            "prerequisite_archives": [], "environment": environment,
        }
        coverage.validate_verification_record(record, coverage.load_json(root / "support.json"), root)
        records.append((component, record))

    evidence_dir = root / "support/evidence" / f"postgis-macos-publication-{run_id}" / architecture / pg_version
    copies = [
        (verification_artifact / "publication/attempt.json", evidence_dir / "attempt.json"),
        (verification_artifact / "publication/postgis-macos-verification.json", evidence_dir / "postgis-macos-verification.json"),
        (verification_artifact / "static-analysis.json", evidence_dir / "static-analysis.json"),
        (probe, evidence_dir / "probe-output.txt"), (raster, evidence_dir / "raster-probe.txt"),
        (runner_image_evidence, evidence_dir / "runner-image.txt"),
        (build_artifact / "core/target.json", evidence_dir / "core-target.json"),
    ]
    for source, destination in copies:
        _retain(source, destination)
    receipt_path = evidence_dir / "current-receipt.json"
    _write_json(receipt_path, receipt)
    destinations = [receipt_path]
    for component, record in records:
        destination = root / "support/verification" / (
            f"{component}-{EXTENSION_VERSION}-postgresql-{pg_version}-macos-{architecture}-current-{run_id}.json")
        _write_json(destination, record)
        destinations.append(destination)
    return [str(path.relative_to(root)) for path in destinations]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--build-artifact", type=Path, required=True)
    parser.add_argument("--verification-artifact", type=Path, required=True)
    parser.add_argument("--runner-image-evidence", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target", type=Path, help="selected architecture target JSON (defaults to arm64)")
    args = parser.parse_args()
    try:
        print("\n".join(import_run(args.root, args.build_artifact, args.verification_artifact,
                                   args.runner_image_evidence, args.run_id, args.target)))
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"macOS PostGIS publication import: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
