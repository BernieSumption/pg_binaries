#!/usr/bin/env python3
"""Check PostGIS payload provenance in an extracted archive."""

import json
from pathlib import Path
import re
import sys
from urllib.parse import quote


root = Path(sys.argv[1]).resolve()
inventory = json.loads((root / "LICENSES/postgis/inventory.json").read_text(encoding="utf-8"))
if inventory.get("schema_version") != 1:
    raise SystemExit("unsupported PostGIS licence inventory schema")
components = inventory.get("components")
if not isinstance(components, list):
    raise SystemExit("PostGIS licence components are missing")

mapped_paths = set()
runtime_paths = set()
postgis_entries = 0
data_packages = set()
for entry in components:
    kind = entry.get("component")
    paths = entry.get("payload_paths")
    if not isinstance(paths, list) or not paths:
        raise SystemExit("component has no payload paths")
    license_path = entry.get("license_file", "")
    if not license_path.startswith("LICENSES/postgis/") or not (root / license_path).is_file():
        raise SystemExit(f"component lacks licence text: {entry}")
    if not (root / license_path).stat().st_size:
        raise SystemExit(f"empty licence text: {license_path}")
    copyright_text = (root / license_path).read_text(encoding="utf-8", errors="replace")
    for name in re.findall(r"/usr/share/common-licenses/([A-Za-z0-9.+-]+)", copyright_text):
        common_license = root / "LICENSES/postgis/common-licenses" / name.rstrip(".,;:")
        if not common_license.is_file() or not common_license.stat().st_size:
            raise SystemExit(f"missing referenced licence text: {common_license}")
    for relative in paths:
        if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
            raise SystemExit(f"invalid payload path: {relative}")
        if relative in mapped_paths or not (root / relative).exists():
            raise SystemExit(f"duplicate or missing payload path: {relative}")
        mapped_paths.add(relative)
        if relative.startswith("lib/runtime/"):
            runtime_paths.add(relative)
    if kind == "postgis":
        postgis_entries += 1
        if (entry.get("version"), entry.get("source_url")) != (
            "3.6.4", "https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz"
        ) or not re.fullmatch("[0-9a-f]{64}", entry.get("source_sha256", "")):
            raise SystemExit("invalid PostGIS source identity")
    elif kind == "ubuntu-package":
        package = entry.get("package", "")
        version = entry.get("version", "")
        source_package = entry.get("source_package", "")
        source_version = entry.get("source_version", "")
        if not all(isinstance(value, str) and value for value in (
            package, version, source_package, source_version
        )):
            raise SystemExit(f"incomplete Ubuntu package identity: {entry}")
        expected_url = (
            f"https://launchpad.net/ubuntu/+source/{quote(source_package, safe='')}/"
            f"{quote(source_version, safe='')}"
        )
        if entry.get("source_url") != expected_url:
            raise SystemExit(f"invalid source URL for {package}")
        if package in ("proj-data", "gdal-data"):
            data_packages.add(package)
    else:
        raise SystemExit(f"unknown component kind: {kind}")

actual_runtime = {
    path.relative_to(root).as_posix()
    for path in (root / "lib/runtime").iterdir() if path.is_file()
}
actual_modules = {
    path.relative_to(root).as_posix() for path in (root / "lib").glob("*.so")
}
if runtime_paths != actual_runtime or not actual_modules.issubset(mapped_paths):
    raise SystemExit("unmapped runtime library or PostGIS SQL module")
if postgis_entries != 1 or data_packages != {"proj-data", "gdal-data"}:
    raise SystemExit("missing PostGIS or required coordinate data component")
if not {"share/extension", "share/proj", "share/gdal"}.issubset(mapped_paths):
    raise SystemExit("unmapped SQL or coordinate data directory")
print(f"Checked PostGIS source and licence mapping for {len(components)} components")
