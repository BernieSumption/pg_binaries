#!/usr/bin/env python3
"""Inspect the exact PostgreSQL and pgTAP Windows publication archives."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile

import coverage
import emit_pgtap_windows_publication as publication


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect(core_archive, extension_archive, report_path):
    core_archive, extension_archive, report_path = map(Path, (core_archive, extension_archive, report_path))
    expected_core = f"postgresql-{publication.PG_VERSION}-{publication.PLATFORM}.tar.gz"
    expected_extension = (f"pgtap-{publication.PGTAP_VERSION}-postgresql-"
                          f"{publication.PG_VERSION}-{publication.PLATFORM}.tar.gz")
    if core_archive.name != expected_core or extension_archive.name != expected_extension:
        raise coverage.CoverageError("archive basenames do not match the pinned target")
    digests = {core_archive.name: sha256_file(core_archive),
               extension_archive.name: sha256_file(extension_archive)}
    if digests[core_archive.name] != publication.CORE_SHA256:
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
                "component": "postgresql", "version": publication.PG_VERSION,
                "postgresql_version": publication.PG_VERSION, "platform": "windows",
                "architecture": publication.ARCHITECTURE, "build_id": "github-39089826690-1",
                "source_revision": "01fe5d267c30f73bb6e44d2b37c18f008223bc75",
            }
            if not isinstance(core, dict) or any(core.get(key) != value for key, value in expected_manifest.items()):
                raise coverage.CoverageError("core archive manifest differs from the pinned build")
            inspected.append("postgresql/manifest.json")
        with tarfile.open(extension_archive, "r:gz") as archive:
            members = archive.getmembers()
            names = {m.name for m in members}
            if len(names) != len(members):
                raise coverage.CoverageError("pgTAP archive contains duplicate paths")
            for member in members:
                path = PurePosixPath(member.name)
                if (path.is_absolute() or ".." in path.parts or "\\" in member.name or
                        member.issym() or member.islnk()):
                    raise coverage.CoverageError("pgTAP archive contains an unsafe path or link")
                if member.name != "metadata.json" and member.name != "pgtap" and not member.name.startswith("pgtap/"):
                    raise coverage.CoverageError("pgTAP archive contains files outside its payload root")
                if member.isfile():
                    inspected.append(member.name)
                    if path.suffix.lower() in {".dll", ".exe", ".so", ".dylib"}:
                        native.append(member.name)
            metadata_member = next((m for m in members if m.name == "metadata.json" and m.isfile()
                                    and m.size <= 1024 * 1024), None)
            if metadata_member is None:
                raise coverage.CoverageError("pgTAP metadata is missing or too large")
            metadata = json.loads(archive.extractfile(metadata_member).read().decode("utf-8"))
            expected = {
                "project": "pgtap", "version": publication.PGTAP_VERSION, "sql_names": ["pgtap"],
                "postgresql_version": publication.PG_VERSION, "platform": "windows",
                "architecture": publication.ARCHITECTURE,
                "source": {"url": publication.SOURCE_URL, "sha256": publication.SOURCE_SHA256},
                "core_archive": {"basename": expected_core, "sha256": publication.CORE_SHA256},
            }
            if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in expected.items()):
                raise coverage.CoverageError("pgTAP metadata does not bind the exact source and core inputs")
            if native:
                raise coverage.CoverageError("SQL-only pgTAP archive contains native code")
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        raise coverage.CoverageError(f"could not inspect final archive: {exc}") from exc
    report = {
        "schema_version": 1, "passed": True, "platform": "windows",
        "architecture": publication.ARCHITECTURE, "archives": digests,
        "inspected_files": sorted(inspected), "native_extension_files": native,
        "checks": ["pinned-core-manifest", "safe-archive-paths", "source-and-core-metadata",
                   "sql-only-extension-payload"],
        "limits": ["PostgreSQL PE dependency closure is verified by the separate Windows core publication."],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--extension-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect(args.core_archive, args.extension_archive, args.output)
        print(f"PASS: inspected {len(report['inspected_files'])} archive files")
        return 0
    except (coverage.CoverageError, OSError, ValueError, TypeError) as exc:
        print(f"pgTAP Windows archive analysis: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
