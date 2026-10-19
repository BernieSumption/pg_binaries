#!/usr/bin/env python3
"""Stage the dSYM bundles indexed for one macOS PostgreSQL core archive."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path, PurePosixPath


CORE_ARCHIVE = re.compile(
    r"postgresql-([0-9]+(?:\.[0-9]+)*)-macos-(arm64|x86_64)\.tar\.gz"
)


def _safe_dsym(root: Path, value: object) -> tuple[PurePosixPath, Path]:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Malformed indexed dSYM path: {value!r}")
    relative = PurePosixPath(value)
    if (relative.is_absolute() or "\\" in value or ":" in value
            or any(part in {"", ".", ".."} for part in relative.parts)
            or relative.suffix != ".dSYM" or relative.parts[0] != "dSYMs"
            or value != relative.as_posix()):
        raise RuntimeError(f"Unsafe indexed dSYM path: {value!r}")
    path = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError(f"Indexed dSYM path contains a symlink: {current}")
    if not path.is_dir():
        raise RuntimeError(f"Indexed dSYM is missing or not a directory: {path}")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"Indexed dSYM escapes artifact directory: {path}") from exc
    for item in path.rglob("*"):
        if item.is_symlink():
            raise RuntimeError(f"Indexed dSYM contains a symlink: {item}")
        if not item.is_file() and not item.is_dir():
            raise RuntimeError(f"Indexed dSYM contains unsupported content: {item}")
    dwarf = path / "Contents/Resources/DWARF"
    if not dwarf.is_dir() or not any(p.is_file() for p in dwarf.iterdir()):
        raise RuntimeError(f"Indexed dSYM has no DWARF content: {path}")
    return relative, path


def stage(artifact_dir: Path, destination: Path, core_archive: str) -> dict:
    if CORE_ARCHIVE.fullmatch(core_archive) is None:
        raise RuntimeError(f"Invalid core archive basename: {core_archive!r}")
    source_root = artifact_dir / "debug-symbols"
    index_path = source_root / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read symbol index {index_path}") from exc
    if (not isinstance(index, dict) or index.get("schema_version") != 1
            or not isinstance(index.get("files"), list) or not index["files"]):
        raise RuntimeError(f"Unsupported or empty symbol index: {index_path}")

    entries = []
    bundles: dict[str, tuple[PurePosixPath, Path, object]] = {}
    for entry in index["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("archive"), str):
            raise RuntimeError("Malformed symbol index entry")
        if entry["archive"] != core_archive:
            continue
        relative, source = _safe_dsym(source_root, entry.get("dsym_path"))
        key = relative.as_posix()
        checksum = entry.get("dsym_sha256")
        if not isinstance(checksum, str) or re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
            raise RuntimeError(f"Malformed indexed dSYM checksum for {key}")
        previous = bundles.get(key)
        if previous is not None and previous[2] != checksum:
            raise RuntimeError(f"Conflicting checksums for indexed dSYM path: {key}")
        bundles[key] = (relative, source, checksum)
        entries.append(entry)
    if not entries:
        raise RuntimeError(f"Symbol index has no entries for core archive {core_archive!r}")

    # Prevent one referenced bundle from occupying another path's parent.
    keys = sorted(bundles)
    for i, key in enumerate(keys):
        if any(other.startswith(key + "/") for other in keys[i + 1:]):
            raise RuntimeError(f"Ambiguous overlapping indexed dSYM paths: {key}")

    destination.mkdir(parents=True, exist_ok=True)
    for relative, source, _checksum in bundles.values():
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.is_symlink() or not target.is_dir():
                raise RuntimeError(f"Unsafe destination dSYM path: {target}")
            shutil.rmtree(target)
        shutil.copytree(source, target, symlinks=False)
    core_index = {**index, "files": entries}
    (destination / "index.json").write_text(
        json.dumps(core_index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return core_index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path, help="Root of downloaded Actions artifact")
    parser.add_argument("destination", type=Path, help="Directory for core-only symbols")
    parser.add_argument("core_archive", help="Exact PostgreSQL core archive basename")
    args = parser.parse_args()
    try:
        stage(args.artifact_dir, args.destination, args.core_archive)
    except RuntimeError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
