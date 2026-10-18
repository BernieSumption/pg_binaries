#!/usr/bin/env python3
"""Check final collection macOS archive identities and Mach-O evidence."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import collection_macos_identity


PG_VERSION, ARCHITECTURE, CORE_IDENTITY = collection_macos_identity.selected_identity()
CORE_NAME = f"postgresql-{PG_VERSION}-macos-{ARCHITECTURE}.tar.gz"
CORE_SHA256 = CORE_IDENTITY["sha256"]
VERSIONS = {
    "1.1.1": "ab99a969334442e4a3c77405bc9ffed0083595d18f3898d64a731353a32bec5e",
    "2.1.3": "a6b07864e5893d3b682bb3223fd6d33015709765c9d40d415c85112358f0e3e4",
}


class EvidenceError(ValueError):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sidecar(path, expected):
    path = Path(path)
    sidecar = path.with_name(path.name + ".sha256")
    match = re.fullmatch(r"([0-9a-f]{64})  ([^\n]+)\n?", sidecar.read_text())
    if not match or match.group(1) != expected or match.group(2) != path.name:
        raise EvidenceError(f"checksum sidecar does not match {path.name}")
    if sha256(path) != expected:
        raise EvidenceError(f"archive checksum does not match {path.name}")


def verify_collection_archive(path, version):
    path = Path(path)
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = {member.name.rstrip("/") for member in members}
        if any(PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts for name in names):
            raise EvidenceError(f"unsafe member path in {path.name}")
        if {name.split("/", 1)[0] for name in names} != {"collection", "metadata.json"}:
            raise EvidenceError(f"unexpected archive roots in {path.name}")
        metadata_member = next((member for member in members if member.name == "metadata.json"), None)
        if not metadata_member or not metadata_member.isfile() or metadata_member.size > 1024 * 1024:
            raise EvidenceError(f"missing or oversized metadata.json in {path.name}")
        metadata = json.load(archive.extractfile(metadata_member))
        expected = {
            "project": "collection", "version": version, "sql_names": ["collection"],
            "requires": [], "configuration_prerequisites": [], "runtime_prerequisites": [],
            "postgresql_version": PG_VERSION, "platform": "macos", "architecture": ARCHITECTURE,
            "source": {
                "url": f"https://github.com/aws/pgcollection/archive/refs/tags/v{version}.tar.gz",
                "sha256": VERSIONS[version],
            },
            "core_archive": {"basename": CORE_NAME, "sha256": CORE_SHA256},
        }
        if metadata != expected:
            raise EvidenceError(f"metadata identity mismatch in {path.name}")
        modules = {name for name in names if re.fullmatch(r"collection/lib/collection\.(?:dylib|so)", name)}
        if len(modules) != 1:
            raise EvidenceError(f"expected one PGXS-selected collection module in {path.name}")
        required = {
            *modules,
            "collection/share/extension/collection.control",
            "collection/LICENSES/pgcollection.txt",
            "collection/LICENSES/pgcollection-NOTICE.txt",
            "collection/LICENSES/uthash.txt",
            "collection/LICENSES/collection-inventory.json",
        }
        if not required <= names:
            raise EvidenceError(f"collection payload is incomplete in {path.name}")
        if any(not member.isfile() and not member.isdir() for member in members):
            raise EvidenceError(f"non-regular collection member in {path.name}")


def verify_report(path, archive_paths):
    report = json.loads(Path(path).read_text())
    expected_archives = {Path(item).name: sha256(item) for item in archive_paths}
    actual_archives = report.get("archives", [])
    if isinstance(actual_archives, list):
        actual_archives = {item.get("basename"): item.get("sha256") for item in actual_archives}
    inspected = report.get("inspected_files", [])
    with tarfile.open(archive_paths[1], "r:gz") as archive:
        module = next(name for name in archive.getnames()
                      if re.fullmatch(r"collection/lib/collection\.(?:dylib|so)", name))
    module_path = module.removeprefix("collection/")
    if (report.get("passed") is not True or report.get("architecture") != ARCHITECTURE
            or not isinstance(inspected, list)
            or not any(item.get("file") == module_path for item in inspected)
            or actual_archives != expected_archives):
        raise EvidenceError(f"static analysis does not pass against final archives: {path}")


def check(core_dir, output_dir):
    core_dir, output_dir = Path(core_dir), Path(output_dir)
    core = core_dir / CORE_NAME
    verify_sidecar(core, CORE_SHA256)
    archives = []
    for version, source_hash in VERSIONS.items():
        archive = output_dir / f"collection-{version}-postgresql-{PG_VERSION}-macos-{ARCHITECTURE}.tar.gz"
        verify_sidecar(archive, sha256(archive))
        verify_collection_archive(archive, version)
        report = output_dir / f"static-analysis-collection-{version}.json"
        verify_report(report, [core, archive])
        archives.append(archive)
    return archives


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core_archives", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        check(args.core_archives, args.output)
    except (EvidenceError, OSError, tarfile.TarError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"collection macOS evidence check: {exc}", file=sys.stderr)
        return 2
    print("PASS: collection macOS archives, checksum sidecars and Mach-O reports match final bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
