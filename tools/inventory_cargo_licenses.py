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
        relative = path.relative_to(root)
        in_license_directory = len(relative.parts) > 1 and relative.parts[0].upper() in {"LICENSES", "LICENCES"}
        if path.is_file() and (LICENSE_FILE.match(path.name) or in_license_directory):
            files.append({
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    return files


def _proc_macro(package):
    return any("proc-macro" in target.get("kind", [])
               or "proc-macro" in target.get("crate_types", [])
               for target in package.get("targets", []))


def dependency_roles(metadata):
    """Classify resolved packages by whether their code is linked or host tooling."""
    resolve = metadata.get("resolve")
    if not isinstance(resolve, dict) or not resolve.get("root"):
        raise ValueError("Cargo metadata must include a resolved root package")

    packages = {package["id"]: package for package in metadata.get("packages", []) if "id" in package}
    nodes = {node["id"]: node for node in resolve.get("nodes", []) if "id" in node}
    root = resolve["root"]
    if root not in packages or root not in nodes:
        raise ValueError("Cargo metadata resolved root is missing from packages or resolve.nodes")

    roles = {package_id: set() for package_id in packages}
    roles[root].update(("root", "shipped"))
    pending = [(root, "shipped")]
    visited = set()
    while pending:
        package_id, context = pending.pop()
        state = (package_id, context)
        if state in visited:
            continue
        visited.add(state)
        node = nodes.get(package_id)
        if node is None:
            continue
        for dep in node.get("deps", []):
            target_id = dep.get("pkg")
            target = packages.get(target_id)
            if target is None:
                continue
            kinds = dep.get("dep_kinds") or [{"kind": None}]
            for dep_kind in kinds:
                kind = dep_kind.get("kind")
                if context == "shipped" and kind not in (None, "normal"):
                    roles[target_id].update(("host_tooling", f"{kind}_dependency"))
                    pending.append((target_id, "host"))
                elif context == "shipped" and _proc_macro(target):
                    roles[target_id].update(("host_tooling", "proc_macro"))
                    pending.append((target_id, "host"))
                elif context == "shipped":
                    roles[target_id].add("shipped")
                    pending.append((target_id, "shipped"))
                else:
                    roles[target_id].update(("host_tooling", f"{kind or 'normal'}_dependency"))
                    if _proc_macro(target):
                        roles[target_id].add("proc_macro")
                    pending.append((target_id, "host"))
    return roles


def inventory(source_root, metadata):
    source_root = source_root.resolve()
    roles = dependency_roles(metadata)
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
            "dependency_roles": sorted(roles.get(package.get("id"), {"unreachable"})),
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
