#!/usr/bin/env python3
"""Map bundled DLLs to their installed vcpkg packages and notices."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

VERSION_FIELDS = ("Version", "Version-String", "Version-Date", "Version-Semver")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_status(path):
    """Read installed/vcpkg/status paragraphs keyed by package and triplet."""
    text = Path(path).read_text(encoding="utf-8")
    packages = {}
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        fields = {}
        for line in paragraph.splitlines():
            if not line or line[0].isspace() or ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key] = value.strip()
        if fields.get("Status") != "install ok installed":
            continue
        name, triplet = fields.get("Package"), fields.get("Architecture")
        if not name or not triplet:
            raise ValueError("installed vcpkg status record lacks Package or Architecture")
        versions = [(field, fields[field]) for field in VERSION_FIELDS
                    if fields.get(field)]
        if len(versions) != 1:
            raise ValueError(
                f"installed vcpkg status record must contain exactly one nonempty version field: "
                f"{name}:{triplet}")
        version = versions[0][1]
        key = (name, triplet)
        record = {
            "port": name,
            "triplet": triplet,
            "version": version,
            "port_version": fields.get("Port-Version", "0"),
        }
        if key in packages and packages[key] != record:
            raise ValueError(f"conflicting installed vcpkg status records: {name}:{triplet}")
        packages[key] = record
    if not packages:
        raise ValueError(f"no installed vcpkg package records found in {path}")
    return packages


def parse_owner_list(path, triplet):
    """Read paths from an installed/vcpkg/info/<package>_<triplet>.list."""
    owners = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        item = raw.strip().replace("\\", "/").lstrip("./")
        if item:
            if item.casefold().startswith(f"{triplet}/".casefold()):
                item = item[len(triplet) + 1:]
            owners.append(item.casefold())
    return owners


def map_bundled_dlls(installed_root, dll_directory):
    installed_root = Path(installed_root).resolve(strict=True)
    dll_directory = Path(dll_directory).resolve(strict=True)
    metadata_root = installed_root.parent / "vcpkg"
    info_dir = metadata_root / "info"
    status_path = metadata_root / "status"
    if not info_dir.is_dir() or not status_path.is_file():
        raise ValueError("expected vcpkg metadata at <installed-root-parent>/vcpkg/info and status")
    packages = parse_status(status_path)
    lists = {}
    for path in sorted(info_dir.glob("*.list"), key=lambda p: p.name.casefold()):
        # Installed-info filenames have appeared both with and without the
        # resolved version between the package name and triplet.
        stem = path.name[:-5]
        matches = []
        for record in packages.values():
            prefix = f"{record['port']}_"
            suffix = f"_{record['triplet']}"
            if not stem.startswith(prefix) or not stem.endswith(suffix):
                continue
            middle = stem[len(prefix):-len(suffix)]
            if middle in ("", record["version"],
                          f"{record['version']}#{record['port_version']}",
                          f"{record['version']}-{record['port_version']}"):
                matches.append(record)
        if len(matches) != 1:
            raise ValueError(f"ownership list has no unique installed package record: {path.name}")
        key = (matches[0]["port"], matches[0]["triplet"])
        if key in lists:
            raise ValueError(f"multiple ownership lists for installed package: {key[0]}:{key[1]}")
        lists[key] = parse_owner_list(path, matches[0]["triplet"])

    dll_paths = sorted(
        (path for path in dll_directory.rglob("*")
         if path.is_file() and path.suffix.casefold() == ".dll"),
        key=lambda p: p.relative_to(dll_directory).as_posix().casefold(),
    )
    if not dll_paths:
        raise ValueError(f"no DLL files found in {dll_directory}")
    result = []
    seen_names = set()
    for dll in dll_paths:
        relative = dll.relative_to(dll_directory).as_posix()
        key_name = dll.name.casefold()
        if key_name in seen_names:
            raise ValueError(f"case-insensitive duplicate bundled DLL basename: {dll.name}")
        seen_names.add(key_name)
        installed_path = f"bin/{dll.name}".casefold()
        owners = [packages[key] for key, paths in lists.items()
                  if installed_path in paths and key in packages]
        if len(owners) != 1:
            raise ValueError(f"bundled DLL must have exactly one vcpkg owner: {relative} (found {len(owners)})")
        package = owners[0]
        notice_relative = f"share/{package['port']}/copyright"
        notice = installed_root / notice_relative
        if not notice.is_file():
            raise ValueError(f"vcpkg copyright notice is missing for {package['port']}: {notice_relative}")
        result.append({
            "dll": relative,
            "dll_sha256": sha256(dll),
            "port": package["port"],
            "triplet": package["triplet"],
            "version": package["version"],
            "port_version": package["port_version"],
            "copyright_file": notice_relative,
            "copyright_sha256": sha256(notice),
        })
    return {"schema_version": 1, "components": result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-root", required=True, help="vcpkg installed triplet root, e.g. installed/x64-windows (metadata is read from its sibling vcpkg directory)")
    parser.add_argument("--dll-directory", required=True, help="directory containing the copied bundled DLLs")
    parser.add_argument("--output", help="write JSON to this path; stdout when omitted")
    args = parser.parse_args(argv)
    try:
        report = map_bundled_dlls(args.installed_root, args.dll_directory)
        payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            Path(args.output).write_text(payload, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(payload)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
