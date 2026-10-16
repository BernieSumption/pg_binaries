#!/usr/bin/env python3
"""Write archive-local provenance for Linux PostgreSQL pilot license texts."""

import json
import pathlib
import subprocess
import sys


root = pathlib.Path(sys.argv[1]).resolve()
postgresql_version = sys.argv[2]
runtime_map = pathlib.Path(sys.argv[3])
components = [{
    "component": "postgresql",
    "version": postgresql_version,
    "payload_paths": ["bin", "include", "lib", "share"],
    "license_file": "PostgreSQL.txt",
    "license_source": (
        f"https://ftp.postgresql.org/pub/source/v{postgresql_version}/"
        f"postgresql-{postgresql_version}.tar.bz2"
    ),
}]

packages = {}
for line in runtime_map.read_text(encoding="utf-8").splitlines():
    package, payload_path = line.split("\t", 1)
    packages.setdefault(package, set()).add(payload_path)

for package, payload_paths in sorted(packages.items()):
    version = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}", package],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if not version:
        raise SystemExit(f"missing installed package version: {package}")
    license_file = f"{package}.copyright"
    license_path = root / "LICENSES" / license_file
    if not license_path.is_file() or not license_path.stat().st_size:
        raise SystemExit(f"missing non-empty license text: {license_path}")
    for payload_path in sorted(payload_paths):
        payload = root / payload_path
        if not payload.is_file() or not payload.stat().st_size:
            raise SystemExit(f"missing non-empty runtime payload: {payload}")
    components.append({
        "component": "runtime-package",
        "package": package,
        "version": version,
        "payload_paths": sorted(payload_paths),
        "license_file": license_file,
        "license_source": f"https://packages.ubuntu.com/jammy/{package}",
    })

postgres_license = root / "LICENSES" / "PostgreSQL.txt"
if not postgresql_version or not postgresql_version[0].isdigit():
    raise SystemExit(f"invalid PostgreSQL version: {postgresql_version}")
if not postgres_license.is_file() or not postgres_license.stat().st_size:
    raise SystemExit(f"missing non-empty license text: {postgres_license}")

inventory = {"schema_version": 1, "components": components}
(root / "LICENSES" / "inventory.json").write_text(
    json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
