#!/usr/bin/env python3
"""Write a deterministic licence and notice inventory from Cargo metadata."""

import argparse
import hashlib
import json
import re
from pathlib import Path


LICENSE_FILE = re.compile(r"^(LICENSE|LICENCE|COPYING|COPYRIGHT|NOTICE)([-.]|$)", re.IGNORECASE)


def file_inventory(root):
    files = []
    if not root.is_dir():
        return files
    for path in sorted(root.rglob("*")):
        if path.is_file() and LICENSE_FILE.match(path.name):
            files.append({
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    return files


def inventory(source_root, metadata):
    source_root = source_root.resolve()
    packages = []
    for package in sorted(metadata.get("packages", []), key=lambda p: (p["name"], p["version"], p.get("source") or "")):
        manifest = Path(package["manifest_path"]).resolve()
        crate_root = manifest.parent
        declared = package.get("license")
        license_file = package.get("license_file")
        if license_file:
            license_path = (crate_root / license_file).resolve()
            if not license_path.is_relative_to(crate_root) or not license_path.is_file() or not license_path.stat().st_size:
                raise ValueError(f"invalid or missing license_file for {package['name']} {package['version']}: {license_file}")
        files = file_inventory(crate_root)
        packages.append({
            "name": package["name"],
            "version": package["version"],
            "source": package.get("source"),
            "license": declared,
            "license_file": Path(license_file).as_posix() if license_file else None,
            "license_metadata_missing": not declared and not license_file,
            "license_notice_files": files,
        })
    return {
        "schema_version": 1,
        "source_files": file_inventory(source_root),
        "packages": packages,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("cargo_metadata", type=Path, help="JSON from cargo metadata --locked --format-version 1")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    metadata = json.loads(args.cargo_metadata.read_text(encoding="utf-8"))
    result = inventory(args.source_root, metadata)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
