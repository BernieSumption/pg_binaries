#!/usr/bin/env python3
"""Stage selected PostGIS runtime files and report conda package owners."""

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


pgroot, conda_prefix, gdal_prefix, temp_root, output = map(Path, sys.argv[1:])
repo = Path(__file__).resolve().parents[2]
closure_root = temp_root / "conda-runtime-closure"
names = ("postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology")
modules = set()
extension = closure_root / "share/extension"
lib = closure_root / "lib"
extension.mkdir(parents=True)
lib.mkdir(parents=True)

for name in names:
    control = pgroot / "share/extension" / f"{name}.control"
    if not control.is_file():
        raise SystemExit(f"missing installed {name}.control")
    match = re.search(r"^\s*module_pathname\s*=\s*['\"]?\$libdir/([^'\"\s]+)", control.read_text(), re.M)
    if match:
        modules.add(match.group(1))
    shutil.copy2(control, extension / control.name)
    for sql in sorted((pgroot / "share/extension").glob(f"{name}--*.sql")):
        modules.update(re.findall(r"\$libdir/([A-Za-z0-9_.-]+)", sql.read_text()))
        shutil.copy2(sql, extension / sql.name)

for module in sorted(modules):
    matches = [pgroot / "lib" / f"{module}{suffix}" for suffix in ("", ".dylib", ".so")]
    matches = [path for path in matches if path.is_file()]
    if len(matches) != 1:
        raise SystemExit(f"expected one installed module for $libdir/{module}: {matches}")
    shutil.copy2(matches[0], lib / matches[0].name)
if not modules:
    raise SystemExit("selected PostGIS SQL files identify no native modules")

environment = os.environ.copy()
environment["PG_MACOS_DEPENDENCY_PREFIX"] = os.pathsep.join((str(gdal_prefix), str(pgroot), str(conda_prefix)))
subprocess.run(
    [sys.executable, str(repo / "experiments/postgis-conda-macos-arm64-2026-10-21/bundle.py"), str(closure_root), "arm64"],
    check=True,
    env=environment,
)

for name, prefix in (("gdal", gdal_prefix), ("proj", conda_prefix)):
    source = prefix / "share" / name
    if not source.is_dir():
        raise SystemExit(f"missing runtime data directory: {source}")
    shutil.copytree(source, closure_root / "share" / name, symlinks=True)

dependencies_path = closure_root / "bundled-dependencies.json"
dependencies = json.loads(dependencies_path.read_text())
shutil.copy2(dependencies_path, output / "bundled-dependencies.json")

records_dir = conda_prefix / "conda-meta"
records = {}
owners = defaultdict(list)
for path in sorted(records_dir.glob("*.json")):
    try:
        record = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        continue
    if not isinstance(record, dict):
        continue
    records[path.name] = record
    filenames = record.get("files", [])
    if not isinstance(filenames, list):
        filenames = []
    paths_data = record.get("paths_data", {})
    if isinstance(paths_data, dict) and isinstance(paths_data.get("paths"), list):
        filenames.extend(item.get("_path") for item in paths_data["paths"] if isinstance(item, dict))
    for filename in filenames:
        if isinstance(filename, str):
            owners[Path(filename).as_posix().removeprefix("./")].append(path.name)

selected_records = set()
unresolved = []


def identify(source, payload):
    path = Path(source)
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        unresolved.append({"payload_path": payload, "source_path": source, "reason": "source path does not resolve"})
        return {"payload_path": payload, "source_path": source, "owner_status": "unresolved"}
    if resolved.is_relative_to(pgroot.resolve()):
        return {"payload_path": payload, "source_path": source, "owner_status": "checked-core"}
    if resolved.is_relative_to(gdal_prefix.resolve()):
        return {"payload_path": payload, "source_path": source, "owner_status": "source-build", "component": "GDAL"}
    if not resolved.is_relative_to(conda_prefix.resolve()):
        unresolved.append({"payload_path": payload, "source_path": source, "reason": "source is outside conda prefix and checked core"})
        return {"payload_path": payload, "source_path": source, "owner_status": "external"}
    relative_candidates = {resolved.relative_to(conda_prefix.resolve()).as_posix()}
    if path.is_relative_to(conda_prefix):
        relative_candidates.add(path.relative_to(conda_prefix).as_posix())
    matches = sorted({record for relative in relative_candidates for record in owners.get(relative, [])})
    if len(matches) == 1:
        selected_records.add(matches[0])
        return {"payload_path": payload, "source_path": source, "owner_status": "conda-package", "conda_meta_record": matches[0]}
    if not matches and resolved.name == "libSFCGAL.2.3.0.dylib":
        return {"payload_path": payload, "source_path": source, "owner_status": "source-build", "component": "SFCGAL"}
    reason = "no conda-meta file owner" if not matches else "multiple conda-meta file owners"
    unresolved.append({"payload_path": payload, "source_path": source, "reason": reason, "matches": matches})
    return {"payload_path": payload, "source_path": source, "owner_status": "unresolved", "matches": matches}


libraries = [identify(source, f"lib/{name}") for name, source in sorted(dependencies.items())]
data_counts = {"share/gdal": Counter(), "share/proj": Counter()}
source_build_data_counts = {"share/gdal": 0, "share/proj": 0}
for directory, prefix in (("share/gdal", gdal_prefix), ("share/proj", conda_prefix)):
    source_root = prefix / directory
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        item = identify(str(path), f"{directory}/{path.relative_to(source_root).as_posix()}")
        if item["owner_status"] == "conda-package":
            data_counts[directory][item["conda_meta_record"]] += 1
        elif item["owner_status"] == "source-build":
            source_build_data_counts[directory] += 1

metadata_root = output / "conda-meta-records"
metadata_root.mkdir(exist_ok=True)
record_summaries = []
for filename in sorted(selected_records):
    source = records_dir / filename
    destination = metadata_root / filename
    shutil.copy2(source, destination)
    record = records[filename]
    record_summaries.append({
        "record": f"conda-meta-records/{filename}",
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "name": record.get("name"),
        "version": record.get("version"),
        "build": record.get("build"),
        "url": record.get("url"),
        "sha256_package": record.get("sha256"),
        "license": record.get("license"),
    })

report = {
    "schema_version": 1,
    "ownership_status": "unresolved" if unresolved else "complete",
    "non_conda_build_sources": [
        json.loads((output / "gdal-source.json").read_text()),
        json.loads((output / "sfcgal-source.json").read_text()),
    ],
    "bundled_libraries": libraries,
    "runtime_data_package_file_counts": {
        directory: {record: count for record, count in sorted(counts.items())}
        for directory, counts in data_counts.items()
    },
    "runtime_data_source_build_file_counts": source_build_data_counts,
    "conda_meta_records": record_summaries,
    "unresolved_files": unresolved,
}
(output / "conda-package-owners.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(f"Recorded {len(libraries)} bundled dylib sources and {len(record_summaries)} conda package owners; unresolved paths: {len(unresolved)}")
