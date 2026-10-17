#!/usr/bin/env python3
"""Check native payload and licence-text coverage in a macOS tar archive."""

import argparse
import json
from pathlib import PurePosixPath
import tarfile


MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}


class InventoryError(ValueError):
    pass


def safe_path(value, label):
    if (not isinstance(value, str) or not value or value.startswith("/")
            or "\\" in value or ".." in PurePosixPath(value).parts):
        raise InventoryError(f"invalid {label}: {value!r}")
    return value.removeprefix("./")


def resolved_member_path(path, target, prefix):
    """Resolve one symlink target and keep it inside its component archive root."""
    if not isinstance(target, str) or not target or target.startswith("/") or "\\" in target:
        raise InventoryError(f"unsafe archive symlink: {path} -> {target!r}")
    parts = list(PurePosixPath(path).parent.parts)
    for part in PurePosixPath(target).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if len(parts) <= len(PurePosixPath(prefix.rstrip("/")).parts):
                raise InventoryError(f"archive symlink escapes component root: {path} -> {target}")
            parts.pop()
        else:
            parts.append(part)
    resolved = PurePosixPath(*parts).as_posix()
    if not resolved.startswith(prefix):
        raise InventoryError(f"archive symlink escapes component root: {path} -> {target}")
    return resolved


def check_archive(archive_path):
    try:
        archive = tarfile.open(archive_path, "r:*")
    except (OSError, tarfile.TarError) as exc:
        raise InventoryError(f"cannot read archive: {exc}") from exc
    with archive:
        members = {}
        for member in archive.getmembers():
            name = safe_path(member.name, "archive member path")
            if name in members:
                raise InventoryError(f"duplicate archive member: {name}")
            members[name] = member

        inventories = [name for name, member in members.items()
                       if name.endswith("/LICENSES/inventory.json") and member.isfile()]
        if len(inventories) != 1:
            raise InventoryError("archive must contain one component LICENSES/inventory.json")
        inventory_name = inventories[0]
        prefix = inventory_name[:-len("LICENSES/inventory.json")]
        links = {name: member.linkname for name, member in members.items() if member.issym()}

        def require_regular(path, origin):
            seen = set()
            current = path
            while current in links:
                if current in seen:
                    raise InventoryError(f"cyclic archive symlink: {origin} -> {current}")
                seen.add(current)
                current = resolved_member_path(current, links[current], prefix)
            target_member = members.get(current)
            if target_member is None or not target_member.isfile():
                raise InventoryError(f"dangling or non-regular archive symlink: {origin} -> {current}")
            return target_member

        handle = archive.extractfile(members[inventory_name])
        try:
            inventory = json.load(handle)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise InventoryError(f"invalid licence inventory JSON: {exc}") from exc
        if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
            raise InventoryError("unsupported macOS licence inventory schema")
        components = inventory.get("components")
        if not isinstance(components, list) or not components:
            raise InventoryError("licence inventory requires components")

        mapped = set()
        for component in components:
            if not isinstance(component, dict):
                raise InventoryError("licence inventory components must be objects")
            paths = component.get("payload_paths")
            if not isinstance(paths, list) or not paths:
                raise InventoryError("component has no payload_paths")
            for raw in paths:
                relative = safe_path(raw, "payload path")
                full = prefix + relative
                member = members.get(full)
                if relative in mapped or member is None or not (member.isfile() or member.issym()):
                    raise InventoryError(f"duplicate or missing payload path: {relative}")
                if member.issym():
                    require_regular(full, relative)
                mapped.add(relative)

            for key in ("license_file", "additional_license_files"):
                declared = component.get(key, [])
                if key == "license_file":
                    declared = [declared]
                if not isinstance(declared, list):
                    raise InventoryError(f"{key} must be a path or list of paths")
                for raw in declared:
                    relative = safe_path(raw, "licence file path")
                    if relative.startswith("LICENSES/"):
                        license_relative = relative
                    else:
                        license_relative = "LICENSES/" + relative
                    member = members.get(prefix + license_relative)
                    if member is None or not member.isfile():
                        raise InventoryError(f"missing or empty declared licence text: {license_relative}")
                    if member.size == 0:
                        raise InventoryError(f"missing or empty declared licence text: {license_relative}")

        native = set()
        for name, member in members.items():
            if not name.startswith(prefix):
                continue
            relative = name[len(prefix):]
            if not relative:
                continue
            base = PurePosixPath(relative).name.lower()
            if base.endswith((".dylib", ".so")):
                native.add(relative)
                continue
            if member.isfile():
                data = archive.extractfile(member).read(4)
                if data in MACHO_MAGICS:
                    native.add(relative)
        missing = sorted(native - mapped)
        if missing:
            raise InventoryError(f"unmapped native payload: {', '.join(missing)}")
        return len(components), len(native)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="final macOS .tar.gz archive")
    args = parser.parse_args()
    try:
        component_count, native_count = check_archive(args.archive)
    except InventoryError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Checked {native_count} native payloads and declared licence texts across {component_count} components; redistribution review remains outside this check")


if __name__ == "__main__":
    main()
