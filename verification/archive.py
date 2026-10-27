#!/usr/bin/env python3
"""Validate that tar.gz package archives can be merged safely."""

from __future__ import annotations

import argparse
import hashlib
import posixpath
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path


class ArchiveError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    kind: str
    mode: int
    value: bytes | str | tuple[int, bytes] | None


def _safe_name(name: str) -> str:
    if "\x00" in name or name.startswith("/") or "\\" in name:
        raise ArchiveError(f"unsafe archive path: {name!r}")
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts[:-1]) or parts[-1] in ("", ".", ".."):
        raise ArchiveError(f"unsafe archive path: {name!r}")
    clean = posixpath.normpath(name)
    if clean != "postgresql" and not clean.startswith("postgresql/"):
        raise ArchiveError(f"member is outside postgresql/: {name!r}")
    return clean


def _safe_link(path: str, target: str, hard: bool) -> str:
    if not target or "\x00" in target or "\\" in target or target.startswith("/"):
        raise ArchiveError(f"unsafe link at {path}: {target!r}")
    if hard:
        resolved = posixpath.normpath(target)
    else:
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
    if resolved != "postgresql" and not resolved.startswith("postgresql/"):
        raise ArchiveError(f"link escapes postgresql/: {path} -> {target}")
    return target


def read_archive(filename: str | Path) -> dict[str, Entry]:
    entries: dict[str, Entry] = {}
    try:
        archive = tarfile.open(filename, mode="r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise ArchiveError(f"cannot read {filename}: {exc}") from exc
    with archive:
        for member in archive:
            path = _safe_name(member.name.rstrip("/") if member.isdir() else member.name)
            if member.isdir():
                entry = Entry("directory", member.mode & 0o7777, None)
            elif member.isfile():
                source = archive.extractfile(member)
                if source is None:
                    raise ArchiveError(f"cannot read file member {path} in {filename}")
                if path == "postgresql/LICENCE":
                    value = source.read(16385)
                    if len(value) > 16384:
                        raise ArchiveError(f"LICENCE pointer is too large in {filename}")
                else:
                    checksum = hashlib.sha256()
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        checksum.update(chunk)
                    value = (member.size, checksum.digest())
                entry = Entry("file", member.mode & 0o7777, value)
            elif member.issym():
                entry = Entry("symlink", member.mode & 0o7777,
                              _safe_link(path, member.linkname, False))
            elif member.islnk():
                target = _safe_link(path, _safe_name(member.linkname), True)
                if entries.get(target, Entry("", 0, None)).kind != "file":
                    raise ArchiveError(f"hard link at {path} lacks an earlier file target in {filename}: {target}")
                entry = Entry("hardlink", member.mode & 0o7777, target)
            else:
                raise ArchiveError(f"unsupported tar member type at {path} in {filename}")
            prior = entries.get(path)
            if prior is not None and prior != entry:
                raise ArchiveError(f"conflicting duplicate path {path} within {filename}")
            entries[path] = entry
    if entries.get("postgresql", Entry("", 0, None)).kind != "directory":
        raise ArchiveError(f"{filename} must contain a postgresql/ directory")
    if "postgresql/LICENCE" not in entries or entries["postgresql/LICENCE"].kind != "file":
        raise ArchiveError(f"{filename} must contain a regular postgresql/LICENCE pointer")
    return entries


def validate_archives(filenames: list[str | Path]) -> dict[str, Entry]:
    if not filenames:
        raise ArchiveError("supply at least one archive")
    merged: dict[str, Entry] = {}
    licence: bytes | None = None
    for filename in filenames:
        current = read_archive(filename)
        pointer = current["postgresql/LICENCE"].value
        if not isinstance(pointer, bytes):
            raise ArchiveError(f"invalid LICENCE pointer in {filename}")
        if b"https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md" not in pointer:
            raise ArchiveError(f"LICENCE pointer does not link to LICENSES.md in {filename}")
        if licence is None:
            licence = pointer
        elif pointer != licence:
            raise ArchiveError(f"postgresql/LICENCE differs in {filename}")
        for path, entry in current.items():
            prior = merged.get(path)
            if prior is not None and prior != entry:
                raise ArchiveError(f"incompatible overlapping path: {path}")
            merged[path] = entry
    for path in merged:
        parts = path.split("/")
        for index in range(1, len(parts)):
            parent = "/".join(parts[:index])
            entry = merged.get(parent)
            if entry is not None and entry.kind != "directory":
                raise ArchiveError(f"non-directory parent of archive path: {parent} -> {path}")
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path, help=".tar.gz archives to validate")
    args = parser.parse_args(argv)
    try:
        validate_archives(args.archives)
    except ArchiveError as exc:
        print(f"archive validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"validated {len(args.archives)} archive(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
