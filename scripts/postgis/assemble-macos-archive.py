#!/usr/bin/env python3
"""Assemble a selected PostGIS macOS archive against its exact PostgreSQL core."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_payload(source, destination):
    for name in ("lib", "share/extension", "share/proj", "share/gdal"):
        source_path = source / name
        if source_path.exists():
            shutil.copytree(source_path, destination / name, dirs_exist_ok=True)


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def remove_absolute_rpaths(root):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or subprocess.run(("lipo", "-archs", str(path)), capture_output=True).returncode:
            continue
        loads = command("otool", "-l", str(path)).splitlines()
        for index, line in enumerate(loads):
            if line.strip() != "cmd LC_RPATH":
                continue
            block = "\n".join(loads[index:index + 6])
            match = re.search(r"^\s*path\s+(\S+)\s+\(offset\s+\d+\)", block, re.M)
            if match and match.group(1).startswith("/") and not match.group(1).startswith(("/usr/lib/", "/System/Library/")):
                subprocess.run(("install_name_tool", "-delete_rpath", match.group(1), str(path)), check=True)
                subprocess.run(("codesign", "--force", "--sign", "-", str(path)), check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("payload_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("postgis_source", type=Path)
    parser.add_argument("core_root", type=Path)
    parser.add_argument("core_archive", type=Path)
    parser.add_argument("core_target", type=Path)
    parser.add_argument("--build-configuration", required=True)
    args = parser.parse_args()

    source, output = args.payload_root.resolve(), args.output.resolve()
    package_root = output / "package"
    package = package_root / "postgis"
    shutil.rmtree(package_root, ignore_errors=True)
    package.mkdir(parents=True)
    copy_payload(source, package)
    owner_report = json.loads((output / "conda-package-owners.json").read_text())
    core_root = args.core_root.resolve()
    core_target = json.loads(args.core_target.read_text())
    architecture = core_target.get("architecture")
    pg_version = core_target.get("postgresql_version")
    if architecture not in {"arm64", "x86_64"} or pg_version not in {"15.19", "16.15", "17.11", "18.6"}:
        raise SystemExit("selected core target has unsupported macOS identity")
    if (core_target.get("project") != "PostGIS" or core_target.get("extension_version") != "3.6.4"
            or core_target.get("platform") != f"macos-{architecture}"
            or core_target.get("core_archive", {}).get("basename") != f"postgresql-{pg_version}-macos-{architecture}.tar.gz"):
        raise SystemExit("selected core target identity mismatch")
    if sha256(args.core_archive) != core_target["core_archive"]["sha256"]:
        raise SystemExit("selected core archive SHA-256 changed before packaging")
    unresolved = owner_report.get("unresolved_files", [])
    expected_sfcgal = [
        item for item in owner_report.get("bundled_libraries", [])
        if item.get("payload_path") == "lib/libSFCGAL.2.3.0.dylib"
        and item.get("owner_status") == "source-build"
        and item.get("component") == "SFCGAL"
    ]
    if owner_report.get("ownership_status") != "complete" or unresolved or len(expected_sfcgal) != 1:
        raise SystemExit(f"unexpected dependency ownership gaps: {unresolved}")
    for item in owner_report["bundled_libraries"]:
        if item.get("owner_status") != "checked-core":
            continue
        library = Path(item["payload_path"]).name
        path = core_root / "lib" / library
        staged = package / "lib" / library
        if not path.is_file() or not staged.is_file() or sha256(path) != sha256(staged):
            raise SystemExit(f"checked-core dependency differs from selected core: {library}")
        staged.unlink()

    # These dependencies have the same library install names as the selected
    # core. The fresh-runner relocation test checks the resulting combination.
    for library in (
            "libicudata.78.3.dylib", "libicui18n.78.3.dylib",
            "libicuuc.78.3.dylib", "libzstd.1.5.7.dylib"):
        staged = package / "lib" / library
        if staged.is_file():
            if not (core_root / "lib" / library).is_file():
                raise SystemExit(f"selected core lacks {library}")
            staged.unlink()

    remove_absolute_rpaths(package / "lib")
    subprocess.run(("python3", str(Path(__file__).resolve().parents[2] / "tools/license_pointer.py"),
                    "write", str(package), "postgis"), check=True)

    core = core_target["core_archive"]
    metadata = {
        "project": "postgis", "version": "3.6.4",
        "sql_names": ["postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology"],
        "requires": [], "configuration_prerequisites": [], "runtime_prerequisites": [
            {"type": "environment_variable", "name": "PROJ_DATA", "value_relative_to_prefix": "share/proj"},
            {"type": "environment_variable", "name": "PROJ_LIB", "value_relative_to_prefix": "share/proj"},
            {"type": "environment_variable", "name": "GDAL_DATA", "value_relative_to_prefix": "share/gdal"},
        ], "postgresql_version": pg_version, "platform": "macos", "architecture": architecture,
        "build_id": f"github-{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}",
        "source_revision": os.environ["GITHUB_SHA"],
        "build_configuration": args.build_configuration,
        "source": {"url": "https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz", "sha256": sha256(args.postgis_source)},
        "core_archive": {"basename": core["basename"], "sha256": core["sha256"]},
    }
    (package_root / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    archive = output / f"postgis-3.6.4-postgresql-{pg_version}-macos-{architecture}.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        stream.add(package, arcname="postgis", recursive=True)
        stream.add(package_root / "metadata.json", arcname="metadata.json")
    subprocess.run(("python3", str(Path(__file__).resolve().parents[2] / "tools/license_pointer.py"),
                    "verify", str(archive), "postgis"), check=True)
    (output / f"{archive.name}.sha256").write_text(f"{sha256(archive)}  {archive.name}\n")
    shutil.rmtree(package_root)
    print(f"Created selected PostGIS archive: {archive}")


if __name__ == "__main__":
    main()
