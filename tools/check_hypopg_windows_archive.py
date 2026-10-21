#!/usr/bin/env python3
"""Inspect the exact PostgreSQL and hypopg Windows publication archives."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile

import coverage
from hypopg_windows_symbols import verify_symbols
import emit_hypopg_windows_publication as publication
from license_pointer import LicensePointerError, verify_archive as verify_license_pointer


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect(core_archive, extension_archive, report_path, pe_report_path=None, pdb_path=None, target=None):
    target = publication if target is None else target
    core_archive, extension_archive, report_path = map(Path, (core_archive, extension_archive, report_path))
    expected_core = f"postgresql-{target.PG_VERSION}-{publication.PLATFORM}.tar.gz"
    expected_extension = (f"hypopg-{publication.HYPOPG_VERSION}-postgresql-"
                          f"{target.PG_VERSION}-{publication.PLATFORM}.tar.gz")
    if core_archive.name != expected_core or extension_archive.name != expected_extension:
        raise coverage.CoverageError("archive basenames do not match the pinned target")
    digests = {core_archive.name: sha256_file(core_archive),
               extension_archive.name: sha256_file(extension_archive)}
    if digests[core_archive.name] != target.CORE_SHA256:
        raise coverage.CoverageError("core archive checksum differs from the pinned input")
    inspected = []
    native = []
    try:
        with tarfile.open(core_archive, "r:gz") as archive:
            core_members = archive.getmembers()
            if len({member.name for member in core_members}) != len(core_members):
                raise coverage.CoverageError("core archive contains duplicate paths")
            for member in core_members:
                path = PurePosixPath(member.name)
                if (path.is_absolute() or ".." in path.parts or "\\" in member.name or
                        member.issym() or member.islnk()):
                    raise coverage.CoverageError("core archive contains an unsafe path or link")
            manifest = next((m for m in archive.getmembers()
                             if m.name == "postgresql/manifest.json" and m.isfile() and m.size < 1024 * 1024), None)
            if manifest is None:
                raise coverage.CoverageError("core archive manifest is missing")
            core = json.loads(archive.extractfile(manifest).read().decode("utf-8"))
            expected_manifest = {
                "component": "postgresql", "version": target.PG_VERSION,
                "postgresql_version": target.PG_VERSION, "platform": "windows",
                "architecture": publication.ARCHITECTURE, "build_id": target.CORE_BUILD_ID,
                "source_revision": target.CORE_SOURCE_REVISION,
            }
            if not isinstance(core, dict) or any(core.get(key) != value for key, value in expected_manifest.items()):
                raise coverage.CoverageError("core archive manifest differs from the pinned build")
            inspected.append("postgresql/manifest.json")
            try:
                verify_license_pointer(core_archive, "postgresql")
            except LicensePointerError as exc:
                raise coverage.CoverageError(f"PostgreSQL licence pointer is invalid: {exc}") from exc
        with tarfile.open(extension_archive, "r:gz") as archive:
            members = archive.getmembers()
            names = {m.name for m in members}
            if len(names) != len(members):
                raise coverage.CoverageError("hypopg archive contains duplicate paths")
            for member in members:
                path = PurePosixPath(member.name)
                if (path.is_absolute() or ".." in path.parts or "\\" in member.name or
                        member.issym() or member.islnk()):
                    raise coverage.CoverageError("hypopg archive contains an unsafe path or link")
                if member.name != "metadata.json" and member.name != "hypopg" and not member.name.startswith("hypopg/"):
                    raise coverage.CoverageError("hypopg archive contains files outside its payload root")
                if member.isfile():
                    inspected.append(member.name)
                    if path.suffix.lower() in {".dll", ".exe", ".so", ".dylib"}:
                        native.append(member.name)
            metadata_member = next((m for m in members if m.name == "metadata.json" and m.isfile()
                                    and m.size <= 1024 * 1024), None)
            if metadata_member is None:
                raise coverage.CoverageError("hypopg metadata is missing or too large")
            metadata = json.loads(archive.extractfile(metadata_member).read().decode("utf-8"))
            expected = {
                "project": "hypopg", "version": publication.HYPOPG_VERSION, "sql_names": ["hypopg"],
                "postgresql_version": target.PG_VERSION, "platform": "windows",
                "architecture": publication.ARCHITECTURE,
                "source": {"url": publication.SOURCE_URL, "sha256": publication.SOURCE_SHA256},
                "core_archive": {"basename": expected_core, "sha256": target.CORE_SHA256},
                "release_eligible": False,
                "core_status": target.CORE_STATUS,
            }
            if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in expected.items()):
                raise coverage.CoverageError("hypopg metadata does not bind the exact source and core inputs")
            if native != ["hypopg/lib/hypopg.dll"]:
                raise coverage.CoverageError("archive must contain exactly the hypopg extension DLL")
            try:
                verify_license_pointer(extension_archive, "hypopg")
            except LicensePointerError as exc:
                raise coverage.CoverageError(f"HypoPG licence pointer is invalid: {exc}") from exc
            required = {"hypopg/lib/hypopg.dll",
                        "hypopg/share/extension/hypopg.control"}
            if not required.issubset(names) or not any(
                    name.startswith("hypopg/share/extension/hypopg") and name.endswith(".sql")
                    for name in names):
                raise coverage.CoverageError("archive is missing the DLL, control file or installation SQL")
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"could not inspect final archive: {exc}") from exc
    pe_digest = None
    if pe_report_path is not None:
        pe_report_path = Path(pe_report_path)
        try:
            pe_report = json.loads(pe_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise coverage.CoverageError(f"PE dependency report is missing or invalid: {exc}") from exc
        pe_archives = {item.get("basename"): item.get("sha256") for item in pe_report.get("archives", [])
                       if isinstance(item, dict)}
        if (pe_report.get("outcome") != "passed" or pe_archives != digests
                or "lib/hypopg.dll" not in pe_report.get("inspected_files", [])):
            raise coverage.CoverageError("PE dependency report does not pass for the exact core and extension archives")
        pe_digest = sha256_file(pe_report_path)
    symbols = verify_symbols(extension_archive, pdb_path or extension_archive.parent / "hypopg.pdb")
    report = {
        "symbols": symbols,
        "schema_version": 1, "passed": True, "platform": "windows",
        "architecture": publication.ARCHITECTURE, "archives": digests,
        "inspected_files": sorted(inspected), "native_extension_files": sorted(native),
        "pe_dependency_analysis_sha256": pe_digest,
        "checks": ["current-profile-core-manifest", "safe-archive-paths", "source-and-core-metadata",
                   "core-and-component-licence-pointers", "native-extension-identity",
                   "archive-bound-pe-dependency-analysis", "archive-bound-pdb-identity"],
        "limits": ["The PostgreSQL PE dependency checker separately inspects the relocated core plus extension DLL."],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgresql-version", choices=publication.PG_VERSIONS, default="18.6")
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--extension-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pe-report", type=Path, required=True)
    parser.add_argument("--pdb", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect(args.core_archive, args.extension_archive, args.output, args.pe_report, args.pdb, target=publication.load_target(args.postgresql_version))
        print(f"PASS: inspected {len(report['inspected_files'])} archive files")
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError, RuntimeError) as exc:
        print(f"hypopg Windows archive analysis: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
