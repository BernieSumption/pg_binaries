#!/usr/bin/env python3
"""Select, validate and stage one extension archive into a PostgreSQL prefix."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tarfile
from urllib.parse import urlparse

class StagingError(ValueError):
    pass


class SelectionError(StagingError):
    pass


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_member_path(member):
    path = Path(member.name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise StagingError(f"unsafe archive path: {member.name!r}")
    if member.issym() or member.islnk():
        target = Path(member.linkname)
        if target.is_absolute():
            raise StagingError(f"absolute archive link: {member.name!r}")
        resolved = (path.parent / target) if member.issym() else target
        depth = 0
        for part in resolved.parts:
            if part == "..":
                depth -= 1
            elif part not in ("", "."):
                depth += 1
            if depth < 0:
                raise StagingError(f"archive link escapes its root: {member.name!r}")
    return path


def _extract_checked(archive_path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names = set()
        for member in members:
            path = _archive_member_path(member)
            if path in names:
                raise StagingError(f"duplicate archive path: {member.name!r}")
            names.add(path)
            if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                raise StagingError(f"unsupported archive member type: {member.name!r}")
        archive.extractall(destination, members=members)


def _metadata(archive_root, project, version, platform, architecture, sql_name):
    entries = {path.name for path in archive_root.iterdir()}
    if entries != {project, "metadata.json"} or not (archive_root / project).is_dir():
        raise StagingError("extension archive must contain its project payload and metadata.json")
    try:
        metadata = json.loads((archive_root / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StagingError("extension metadata is missing or invalid JSON") from exc
    expected = {"project": project, "version": version, "platform": platform,
                "architecture": architecture}
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise StagingError(f"extension metadata mismatch for {key}")
    if sql_name not in metadata.get("sql_names", []):
        raise StagingError(f"extension metadata does not provide SQL name {sql_name!r}")
    for key in ("requires", "configuration_prerequisites", "runtime_prerequisites"):
        if not isinstance(metadata.get(key), list):
            raise StagingError(f"extension metadata field {key} must be an array")
    return archive_root / project


def merge_payload(payload, prefix):
    """Merge a payload into a prefix, allowing directory merges only."""
    payload = Path(payload)
    prefix = Path(prefix)
    if not payload.is_dir():
        raise StagingError(f"extension payload directory is missing: {payload}")
    prefix.mkdir(parents=True, exist_ok=True)

    def check_collisions(source, destination):
        for entry in source.iterdir():
            target = destination / entry.name
            if entry.is_dir() and not entry.is_symlink():
                if target.exists() or target.is_symlink():
                    if target.is_symlink() or not target.is_dir():
                        raise StagingError(f"extension payload collision: {target.relative_to(prefix)}")
                check_collisions(entry, target)
            elif target.exists() or target.is_symlink():
                raise StagingError(f"extension payload collision: {target.relative_to(prefix)}")

    def merge(source, destination):
        for entry in source.iterdir():
            target = destination / entry.name
            if entry.is_dir() and not entry.is_symlink():
                if not target.exists():
                    target.mkdir(mode=entry.stat().st_mode & 0o7777)
                merge(entry, target)
                shutil.copystat(entry, target, follow_symlinks=False)
            else:
                if entry.is_symlink():
                    target.symlink_to(entry.readlink())
                else:
                    shutil.copy2(entry, target)

    check_collisions(payload, prefix)
    merge(payload, prefix)


def _relocate_licenses(payload, project):
    """Place extension licence evidence below LICENSES/<project>."""
    licenses = payload / "LICENSES"
    if not licenses.exists() and not licenses.is_symlink():
        raise StagingError("extension payload is missing LICENSES/inventory.json")
    if licenses.is_symlink() or not licenses.is_dir():
        raise StagingError("extension LICENSES path must be a directory")

    destination = licenses / project
    if destination.exists() and (destination.is_symlink() or not destination.is_dir()):
        raise StagingError(f"extension licence path collision: LICENSES/{project}")
    destination.mkdir(exist_ok=True)
    for entry in list(licenses.iterdir()):
        if entry == destination:
            continue
        target = destination / entry.name
        if target.exists() or target.is_symlink():
            raise StagingError(f"extension licence path collision: LICENSES/{project}/{entry.name}")
    for entry in list(licenses.iterdir()):
        if entry == destination:
            continue
        entry.rename(destination / entry.name)
    inventory = destination / "inventory.json"
    if inventory.is_symlink() or not inventory.is_file():
        raise StagingError("extension payload is missing LICENSES/inventory.json")


def select_and_stage(inventory, support, postgresql_version, platform_key,
                     project, extension_version, sql_name, archive_directory,
                     prefix, staging_root):
    """Resolve a selected archive from inventory, verify it, then merge it."""
    selector_spec = importlib.util.spec_from_file_location(
        "staging_archive_selector", Path(__file__).with_name("select_extension_archive.py"))
    selector = importlib.util.module_from_spec(selector_spec)
    selector_spec.loader.exec_module(selector)
    try:
        download = selector.select_archive(inventory, support, postgresql_version,
                                           platform_key, project, extension_version, sql_name)
    except selector.SelectionError as exc:
        raise SelectionError(str(exc)) from exc
    url = download.get("url")
    filename = Path(urlparse(url).path).name if isinstance(url, str) else ""
    if not filename or filename in (".", ".."):
        raise StagingError("selected inventory download has no archive filename")
    archive_path = Path(archive_directory) / filename
    if not archive_path.is_file():
        raise StagingError(f"selected extension archive is missing: {filename}")
    expected_digest = download.get("sha256")
    if not isinstance(expected_digest, str) or _digest(archive_path) != expected_digest.lower():
        raise StagingError(f"selected extension archive checksum mismatch: {filename}")

    platform, separator, architecture = platform_key.partition("-")
    if not separator or not architecture:
        raise StagingError(f"invalid platform key: {platform_key!r}")
    if len(expected_digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in expected_digest):
        raise StagingError("selected inventory download has an invalid SHA-256")
    stage_path = Path(staging_root) / f"{project}-{extension_version}-{expected_digest[:12]}"
    if stage_path.exists():
        shutil.rmtree(stage_path)
    _extract_checked(archive_path, stage_path)
    payload = _metadata(stage_path, project.lower().replace(" ", "_"),
                        extension_version, platform, architecture, sql_name)
    _relocate_licenses(payload, project.lower().replace(" ", "_"))
    merge_payload(payload, prefix)
    return download


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--merge-payload", type=Path)
    mode.add_argument("--inventory", type=Path,
                      help="inventory JSON used to select an extension archive")
    parser.add_argument("--support", type=Path,
                        help="support JSON used to validate the selected target")
    parser.add_argument("--postgresql-version")
    parser.add_argument("--platform")
    parser.add_argument("--project")
    parser.add_argument("--extension-version")
    parser.add_argument("--sql-name")
    parser.add_argument("--archive-directory", type=Path)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path)
    args = parser.parse_args()
    try:
        if args.merge_payload is not None:
            merge_payload(args.merge_payload, args.prefix)
            return 0

        required = ("support", "postgresql_version", "platform", "project",
                    "extension_version", "sql_name", "archive_directory", "staging_root")
        missing = [option.replace("_", "-") for option in required
                   if getattr(args, option) is None]
        if missing:
            parser.error("inventory mode requires --" + ", --".join(missing))
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        support = json.loads(args.support.read_text(encoding="utf-8"))
        download = select_and_stage(
            inventory, support, args.postgresql_version, args.platform,
            args.project, args.extension_version, args.sql_name,
            args.archive_directory, args.prefix, args.staging_root)
        print(json.dumps(download, sort_keys=True))
        return 0
    except StagingError as exc:
        print(f"stage-extension-archive: error: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"stage-extension-archive: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
