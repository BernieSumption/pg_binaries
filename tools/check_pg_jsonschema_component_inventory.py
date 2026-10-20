#!/usr/bin/env python3
"""Validate the project-named redistribution inventory in a pg_jsonschema archive."""

import argparse
import json
import tarfile
from pathlib import Path, PurePosixPath


INVENTORY = "pg_jsonschema/LICENSES/pg_jsonschema-inventory.json"
CARGO_INVENTORY = "pg_jsonschema/LICENSES/cargo/cargo-license-inventory.json"
REVIEWED_LICENSES = {
    "(MIT OR Apache-2.0) AND Unicode-3.0", "Apache-2.0", "Apache-2.0 OR BSL-1.0",
    "Apache-2.0 OR MIT", "Apache-2.0/MIT", "BSD-2-Clause OR Apache-2.0 OR MIT",
    "MIT", "MIT OR Apache-2.0", "MIT-0", "MIT/Apache-2.0", "Unicode-3.0",
    "Unlicense OR MIT", "Zlib",
}


def validate(archive_path, expected_inventory_path=None):
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {}
        for member in archive.getmembers():
            name = member.name.rstrip("/")
            if name in members:
                raise ValueError(f"duplicate archive member: {name}")
            members[name] = member

        def read_json(path):
            member = members.get(path)
            if member is None or not member.isfile() or member.size <= 0 or member.size > 8 * 1024 * 1024:
                raise ValueError(f"missing or invalid inventory: {path}")
            return json.load(archive.extractfile(member))

        def license_member(path):
            relative = PurePosixPath(path)
            if (relative.is_absolute() or "\\" in path
                    or any(part in ("", ".", "..") for part in relative.parts)):
                raise ValueError(f"unsafe licence path: {path}")
            name = path if path.startswith("LICENSES/") else f"LICENSES/{path}"
            member = members.get(f"pg_jsonschema/{name}")
            if member is None or not member.isfile() or member.size <= 0:
                raise ValueError(f"missing non-empty licence evidence: {name}")
            return name.removeprefix("LICENSES/")

        inventory = read_json(INVENTORY)
        metadata = read_json("metadata.json")
        platform = metadata.get("platform") if isinstance(metadata, dict) else None
        if platform not in {"linux", "macos"}:
            raise ValueError("pg_jsonschema archive has an unsupported platform")
        if expected_inventory_path is not None:
            expected = Path(expected_inventory_path).read_bytes()
            embedded = archive.extractfile(members[INVENTORY]).read()
            if embedded != expected:
                raise ValueError("retained component inventory differs from the archive member")
        if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
            raise ValueError("project inventory schema_version must be 1")
        components = inventory.get("components")
        if not isinstance(components, list) or len(components) != 1:
            raise ValueError("project inventory must contain one pg_jsonschema component")
        component = components[0]
        if (not isinstance(component, dict) or component.get("component") != "pg_jsonschema"
                or component.get("version") != "0.3.4"):
            raise ValueError("component identity must be pg_jsonschema 0.3.4")
        payload_paths = component.get("payload_paths")
        if (not isinstance(payload_paths, list) or len(payload_paths) != 2
                or payload_paths[1] != "share/extension"
                or payload_paths[0] not in ({"lib/pg_jsonschema.so"} if platform == "linux"
                                            else {"lib/pg_jsonschema.so", "lib/pg_jsonschema.dylib"})):
            raise ValueError("component payload_paths do not match a supported pg_jsonschema module")
        if not all(any(name == f"pg_jsonschema/{path}" or name.startswith(f"pg_jsonschema/{path}/")
                       for name in members) for path in payload_paths):
            raise ValueError("component payload path is missing from the archive")

        primary = component.get("license_file")
        if primary != "pg_jsonschema/LICENSE":
            raise ValueError("component license_file must identify the upstream project licence")
        license_member(primary)
        additional = component.get("additional_license_files")
        if (not isinstance(additional, list) or not additional
                or not all(isinstance(path, str) and path for path in additional)
                or len(additional) != len(set(additional))):
            raise ValueError("component additional_license_files must be a non-empty unique list")
        normalized = {license_member(path) for path in additional}

        cargo = read_json(CARGO_INVENTORY)
        packages = cargo.get("packages") if isinstance(cargo, dict) else None
        if not isinstance(packages, list) or not packages:
            raise ValueError("Cargo inventory has no packages")
        expected = set()
        for package in packages:
            if not isinstance(package, dict):
                raise ValueError("Cargo inventory package entry must be an object")
            roles = package.get("dependency_roles", [])
            if not isinstance(roles, list):
                raise ValueError("Cargo dependency_roles must be a list")
            if "shipped" not in roles:
                continue
            if not all(isinstance(package.get(field), str) and package[field]
                       for field in ("name", "version")):
                raise ValueError("shipped Cargo package requires name and version")
            license_expression = package.get("license")
            root_declaration = (package["name"] == "pg_jsonschema" and package["version"] == "0.3.4"
                                and license_expression is None)
            if license_expression not in REVIEWED_LICENSES and not root_declaration:
                raise ValueError(f"shipped crate licence requires review: {package['name']}")
            prefix = f"cargo/{package['name']}-{package['version']}"
            notices = package.get("packaged_license_notice_files")
            if not isinstance(notices, list) or not notices:
                raise ValueError(f"shipped crate lacks packaged notices: {package['name']}")
            for notice in notices:
                path = notice.get("path") if isinstance(notice, dict) else None
                if not isinstance(path, str) or not path:
                    raise ValueError(f"shipped crate has an invalid notice path: {package['name']}")
                expected.add(path if path.startswith(prefix + "/") else f"{prefix}/{path}")
        if normalized != expected:
            raise ValueError("component additional_license_files do not cover the shipped Cargo notices exactly")

        review = component.get("redistribution_review")
        if (not isinstance(review, dict) or review.get("status") != "resolved"
                or not isinstance(review.get("basis"), str) or not review["basis"].strip()
                or review.get("source_obligation") != "none"):
            raise ValueError("component redistribution review must be resolved with source_obligation none")
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    args = parser.parse_args()
    validate(args.archive)


if __name__ == "__main__":
    main()
