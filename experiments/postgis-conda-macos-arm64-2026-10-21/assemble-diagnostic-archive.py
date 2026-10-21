#!/usr/bin/env python3
"""Assemble a non-publication PostGIS archive with declaration-led pending inventory."""

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


def payload_files(root):
    return {path.relative_to(root).as_posix() for top in ("lib", "share")
            for path in (root / top).rglob("*") if path.is_file()}


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
    parser.add_argument("conda_prefix", type=Path)
    parser.add_argument("postgis_source", type=Path)
    parser.add_argument("gdal_source", type=Path)
    parser.add_argument("sfcgal_source", type=Path)
    parser.add_argument("core_root", type=Path)
    parser.add_argument("core_archive", type=Path)
    parser.add_argument("core_target", type=Path)
    args = parser.parse_args()

    source, output, conda = args.payload_root.resolve(), args.output.resolve(), args.conda_prefix.resolve()
    package_root = output / "package"
    package = package_root / "postgis"
    shutil.rmtree(package_root, ignore_errors=True)
    package.mkdir(parents=True)
    copy_payload(source, package)
    licenses = package / "LICENSES"
    licenses.mkdir()

    owner_report = json.loads((output / "conda-package-owners.json").read_text())
    core_root = args.core_root.resolve()
    core_target = json.loads(args.core_target.read_text())
    if sha256(args.core_archive) != core_target["core_archive"]["sha256"]:
        raise SystemExit("selected core archive SHA-256 changed before diagnostic packaging")
    unresolved = owner_report.get("unresolved_files", [])
    expected_sfcgal = [item for item in unresolved if item.get("payload_path") == "lib/libSFCGAL.2.3.0.dylib"]
    if len(expected_sfcgal) != 1 or any(item not in expected_sfcgal for item in unresolved):
        raise SystemExit(f"unexpected dependency ownership gaps: {unresolved}")
    core_inventory = json.loads((core_root / "LICENSES/inventory.json").read_text())
    reused_core = []
    for item in owner_report["bundled_libraries"]:
        if item.get("owner_status") != "checked-core":
            continue
        library = Path(item["payload_path"]).name
        path = core_root / "lib" / library
        staged = package / "lib" / library
        if not path.is_file() or not staged.is_file() or sha256(path) != sha256(staged):
            raise SystemExit(f"checked-core dependency does not match the selected core: {library}")
        owner = next((value for value in core_inventory["components"] if library in value.get("libraries", [])), None)
        if not owner or owner.get("redistribution_review", {}).get("status") != "resolved":
            raise SystemExit(f"selected core has no resolved owner for reused dependency: {library}")
        staged.unlink()
        reused_core.append({"library": library, "sha256": sha256(path), "core_component": owner["component"],
                            "core_version": owner["version"], "license_file": "LICENSES/" + owner["license_file"]})
    records_dir = output / "conda-meta-records"
    records = {path.name: json.loads(path.read_text()) for path in records_dir.glob("*.json")}
    owner_by_path = {}
    for filename, record in records.items():
        paths = record.get("files", [])
        paths += [item.get("_path") for item in record.get("paths_data", {}).get("paths", []) if isinstance(item, dict)]
        for item in paths:
            if isinstance(item, str):
                owner_by_path.setdefault(Path(item).as_posix().removeprefix("./"), set()).add(filename)

    packages = {}
    for item in owner_report["bundled_libraries"]:
        record_name = item.get("conda_meta_record")
        if item.get("owner_status") == "conda-package" and record_name:
            packages.setdefault(record_name, set()).add(item["payload_path"])
    for path in sorted((package / "share/proj").rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(package).as_posix()
        prefix_rel = path.relative_to(package / "share/proj").as_posix()
        matches = owner_by_path.get(f"share/proj/{prefix_rel}", set())
        if len(matches) == 1:
            packages.setdefault(next(iter(matches)), set()).add(rel)
        elif not matches:
            raise SystemExit(f"PROJ runtime file has no unique conda owner: {rel}")
        else:
            raise SystemExit(f"PROJ runtime file has multiple conda owners: {rel}: {sorted(matches)}")

    components = []

    def pending(component, version, paths, license_file, source_url, source_sha, expression, details):
        components.append({
            "component": component, "version": str(version), "payload_paths": sorted(paths),
            "license_file": license_file, "license_expression": expression,
            "source_url": source_url, "source_sha256": source_sha,
            "license_source": details,
            "redistribution_review": {"status": "pending", "basis": "Diagnostic inventory generated from exact source and package metadata; final redistribution review is pending.", "source_obligation": "pending"},
        })

    for filename, paths in sorted(packages.items()):
        record = records[filename]
        if not paths:
            continue
        name, version, build = record["name"], record["version"], record["build"]
        declaration = f"{name}-{version}-{build}-declaration.txt"
        installed_notices = []
        for source_rel in sorted(owner_by_path):
            if filename not in owner_by_path[source_rel]:
                continue
            lower = Path(source_rel).name.lower()
            if lower in {"license", "license.txt", "license.md", "copying", "copyright", "notice"} or lower.startswith(("license.", "copying.")):
                source_file = conda / source_rel
                if source_file.is_file():
                    notice_name = f"{name}-{version}-notice-{len(installed_notices) + 1}.txt"
                    shutil.copy2(source_file, licenses / notice_name)
                    installed_notices.append((source_rel, f"LICENSES/{notice_name}"))
        package_url = record.get("url")
        package_sha = record.get("sha256")
        expression = record.get("license")
        if not package_url or not re.fullmatch(r"[0-9a-f]{64}", package_sha or "") or not expression:
            raise SystemExit(f"incomplete exact package identity or licence declaration: {filename}")
        evidence = (f"Package: {name} {version} ({build})\nChannel: {record.get('channel')}\n"
                    f"Platform: {record.get('subdir')}\nPackage URL: {package_url}\n"
                    f"Package SHA-256: {package_sha}\nDeclared licence: {expression}\n"
                    f"Declaration source: https://anaconda.org/conda-forge/{name}\n"
                    f"Package record SHA-256: {sha256(records_dir / filename)}\n")
        (licenses / declaration).write_text(evidence)
        compact_record = {
            "name": name, "version": version, "build": build,
            "channel": record.get("channel"), "subdir": record.get("subdir"),
            "url": package_url, "sha256": package_sha, "license": expression,
            "payload_paths": sorted(paths),
        }
        records_subdir = licenses / "conda-package-records"
        records_subdir.mkdir(exist_ok=True)
        compact_path = records_subdir / f"{name}-{version}-{build}.json"
        compact_path.write_text(json.dumps(compact_record, indent=2, sort_keys=True) + "\n")
        notice_index = 0
        if "LGPL" in expression:
            notice_index = next((index for index, (path, _) in enumerate(installed_notices)
                                 if "lesser" in Path(path).name.lower() or "lgpl" in Path(path).name.lower()), 0)
        elif expression == "MIT":
            notice_index = next((index for index, (path, _) in enumerate(installed_notices)
                                 if "license" in Path(path).name.lower()), 0)
        primary = installed_notices[notice_index][1] if installed_notices else f"LICENSES/{declaration}"
        additional = [f"LICENSES/{declaration}", f"LICENSES/conda-package-records/{compact_path.name}",
                      *[path for index, (_, path) in enumerate(installed_notices) if index != notice_index]]
        pending(f"conda-{name}", version, paths, primary, package_url, package_sha, expression,
                f"https://anaconda.org/conda-forge/{name}")
        components[-1]["package_license_expression"] = expression
        if additional:
            components[-1]["additional_license_files"] = additional
        components[-1]["package_build"] = build
        components[-1]["package_channel"] = record.get("channel")
        components[-1]["package_record"] = f"LICENSES/conda-package-records/{compact_path.name}"

    for record_name, (component, root_name, source_archive, license_source, license_expr) in {
        "postgis": ("postgis", "postgis", args.postgis_source, "https://postgis.net/about/licence/", "GPL-2.0-or-later"),
        "gdal": ("gdal", "gdal", args.gdal_source, "https://gdal.org/en/stable/license.html", "MIT"),
        "sfcgal": ("sfcgal", "sfcgal", args.sfcgal_source, "https://github.com/CGAL/SFCGAL", "LGPL-2.0-or-later"),
    }.items():
        source_dir = source_archive.parent / ("postgis-3.6.4" if record_name == "postgis" else "gdal-3.13.3" if record_name == "gdal" else next(p.name for p in source_archive.parent.glob("SFCGAL-*") if p.is_dir()))
        license_name = {"postgis": "COPYING", "gdal": "LICENSE.TXT", "sfcgal": "LICENSE"}[record_name]
        source_license = source_dir / license_name
        if not source_license.is_file():
            raise SystemExit(f"missing {record_name} source licence: {source_license}")
        target_name = {"postgis": "PostGIS.txt", "gdal": "GDAL.txt", "sfcgal": "SFCGAL.txt"}[record_name]
        shutil.copy2(source_license, licenses / target_name)
        source_url, source_hash = {
            "postgis": ("https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz", "ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6"),
            "gdal": ("https://download.osgeo.org/gdal/3.13.3/gdal-3.13.3.tar.gz", "5e0c388d83da2d686cc00a40272882432cdb54edff43d4af173e532844a0a0ea"),
            "sfcgal": (json.loads((output / "sfcgal-source.json").read_text())["source_url"], json.loads((output / "sfcgal-source.json").read_text())["source_sha256"]),
        }[record_name]
        source_paths = {
            "postgis": [p for p in payload_files(package) if p.startswith("lib/postgis") or p.startswith("share/extension/")],
            "gdal": [p for p in payload_files(package) if p.startswith("share/gdal/") or Path(p).name.startswith("libgdal")],
            "sfcgal": [p for p in payload_files(package) if Path(p).name.startswith("libSFCGAL")],
        }[record_name]
        pending(component, "3.6.4" if record_name == "postgis" else "3.13.3" if record_name == "gdal" else "2.3.0",
                source_paths, f"LICENSES/{target_name}", source_url, source_hash, license_expr, license_source)

    remove_absolute_rpaths(package / "lib")
    actual = payload_files(package)
    mapped = {path for item in components for path in item["payload_paths"]}
    if actual != mapped:
        raise SystemExit(f"inventory payload mismatch: missing={sorted(actual - mapped)} extra={sorted(mapped - actual)}")
    inventory = {"schema_version": 1, "reused_core_dependencies": reused_core, "components": components}
    (licenses / "postgis-inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")

    core = core_target["core_archive"]
    metadata = {
        "project": "postgis", "version": "3.6.4",
        "sql_names": ["postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology"],
        "requires": [], "configuration_prerequisites": [], "runtime_prerequisites": [
            {"type": "environment_variable", "name": "PROJ_DATA", "value_relative_to_prefix": "share/proj"},
            {"type": "environment_variable", "name": "PROJ_LIB", "value_relative_to_prefix": "share/proj"},
            {"type": "environment_variable", "name": "GDAL_DATA", "value_relative_to_prefix": "share/gdal"},
        ], "postgresql_version": "18.6", "platform": "macos", "architecture": "arm64",
        "build_id": f"github-{os.environ['GITHUB_RUN_ID']}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}",
        "source_revision": os.environ["GITHUB_SHA"],
        "build_configuration": "diagnostic;native-macos;deployment-target=11.0;gdal=3.13.3;gdal-drivers=GTiff,PNG,JPEG;dependencies=conda-forge",
        "source": {"url": "https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz", "sha256": sha256(args.postgis_source)},
        "core_archive": {"basename": core["basename"], "sha256": core["sha256"]},
    }
    (package_root / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    archive = output / "postgis-3.6.4-postgresql-18.6-macos-arm64.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        stream.add(package, arcname="postgis", recursive=True)
        stream.add(package_root / "metadata.json", arcname="metadata.json")
    (output / f"{archive.name}.sha256").write_text(f"{sha256(archive)}  {archive.name}\n")
    shutil.rmtree(package_root)
    print(f"Created diagnostic archive with {len(components)} pending inventory components: {archive}")


if __name__ == "__main__":
    main()
