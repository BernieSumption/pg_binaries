#!/usr/bin/env python3
"""Map the PostGIS pilot payload to its source and included licence files."""

import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote


root = Path(sys.argv[1]).resolve()
runtime_map = Path(sys.argv[2])
postgis_sha256 = sys.argv[3]
if len(postgis_sha256) != 64 or any(c not in "0123456789abcdef" for c in postgis_sha256):
    raise SystemExit("invalid PostGIS source SHA-256")


def package_versions(package):
    fields = "${Version}\t${source:Package}\t${source:Version}"
    result = subprocess.run(
        ["dpkg-query", "-W", f"-f={fields}", package],
        check=True, capture_output=True, text=True,
    ).stdout.strip().split("\t")
    if len(result) != 3 or not all(result):
        raise SystemExit(f"incomplete package identity: {package}: {result}")
    return result


def require_payload(relative):
    path = root / relative
    if not path.exists() or (path.is_file() and not path.stat().st_size):
        raise SystemExit(f"missing or empty payload: {relative}")
    return relative


def require_license(name):
    relative = f"LICENSES/{name}"
    require_payload(relative)
    return relative


def package_entry(package, payload_paths):
    binary_version, source_package, source_version = package_versions(package)
    license_file = require_license(f"{package}.copyright")
    return {
        "component": "ubuntu-package",
        "package": package,
        "version": binary_version,
        "source_package": source_package,
        "source_version": source_version,
        "source_url": (
            f"https://launchpad.net/ubuntu/+source/{quote(source_package, safe='')}/"
            f"{quote(source_version, safe='')}"
        ),
        "payload_paths": sorted(require_payload(path) for path in payload_paths),
        "license_file": license_file,
    }


runtime_packages = {}
mapped_runtime_paths = set()
for line in runtime_map.read_text(encoding="utf-8").splitlines():
    package, relative = line.split("\t", 1)
    if not package or not relative.startswith("lib/runtime/"):
        raise SystemExit(f"invalid runtime mapping: {line}")
    if relative in mapped_runtime_paths:
        raise SystemExit(f"duplicate runtime mapping: {relative}")
    mapped_runtime_paths.add(relative)
    runtime_packages.setdefault(package, set()).add(relative)

actual_runtime_paths = {
    path.relative_to(root).as_posix()
    for path in (root / "lib/runtime").iterdir() if path.is_file()
}
if mapped_runtime_paths != actual_runtime_paths:
    raise SystemExit(
        f"runtime inventory mismatch: missing={sorted(actual_runtime_paths - mapped_runtime_paths)} "
        f"extra={sorted(mapped_runtime_paths - actual_runtime_paths)}"
    )

module_paths = sorted(path.relative_to(root).as_posix() for path in (root / "lib").glob("*.so"))
if not module_paths:
    raise SystemExit("no PostGIS SQL modules found")
components = [{
    "component": "postgis",
    "version": "3.6.4",
    "source_url": "https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz",
    "source_sha256": postgis_sha256,
    "payload_paths": module_paths + [require_payload("share/extension")],
    "license_file": require_license("PostGIS.txt"),
}]
for package, paths in sorted(runtime_packages.items()):
    components.append(package_entry(package, paths))
for package, relative in (("proj-data", "share/proj"), ("gdal-data", "share/gdal")):
    components.append(package_entry(package, [relative]))

inventory = {"schema_version": 1, "components": components}
(root / "LICENSES/inventory.json").write_text(
    json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
