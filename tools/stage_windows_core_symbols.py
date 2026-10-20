#!/usr/bin/env python3
"""Stage only PostgreSQL core PDBs from a downloaded Windows build artifact."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path, PurePosixPath


def _core_archive_names(core_archive: str) -> set[str]:
    match = re.fullmatch(r"postgresql-([0-9]+(?:\.[0-9]+)*)-windows-x86_64\.tar\.gz", core_archive)
    if match is None:
        raise RuntimeError(f"Invalid core archive basename: {core_archive!r}")
    return {core_archive} | {
        # The paired Windows pilot currently packages this pinned pgvector release.
        f"pgvector-0.8.7-postgresql-{match.group(1)}-windows-x86_64.tar.gz"
    }


def _safe_pdb(source: Path, artifact_dir: Path, value: object) -> tuple[PurePosixPath, Path]:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Malformed indexed PDB path: {value!r}")
    relative = PurePosixPath(value)
    if (relative.is_absolute() or "\\" in value or ":" in value
            or any(part in {"", ".", ".."} for part in relative.parts)
            or relative.suffix.lower() != ".pdb"):
        raise RuntimeError(f"Unsafe indexed PDB path: {value!r}")
    path = source.joinpath(*relative.parts)
    try:
        path.relative_to(source)
    except ValueError as exc:
        raise RuntimeError(f"Unsafe indexed PDB path: {value!r}") from exc
    # Check each component so a symlinked parent cannot redirect the copy.
    current = source
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError(f"Indexed PDB path contains a symlink: {current}")
    if not path.is_file():
        raise RuntimeError(f"Indexed PDB is missing or not a regular file: {path}")
    try:
        path.resolve().relative_to(artifact_dir.resolve())
    except ValueError as exc:
        raise RuntimeError(f"Indexed PDB escapes artifact directory: {path}") from exc
    return relative, path


def stage(artifact_dir: Path, destination: Path, core_archive: str) -> dict:
    allowed_archives = _core_archive_names(core_archive)
    index_path = artifact_dir / "debug-symbols" / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read symbol index {index_path}") from exc
    if (not isinstance(index, dict) or index.get("schema_version") != 1
            or not isinstance(index.get("files"), list) or not index["files"]):
        raise RuntimeError(f"Unsupported or empty symbol index: {index_path}")

    selected = []
    paths: dict[str, dict] = {}
    for entry in index["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("archive"), str):
            raise RuntimeError("Malformed symbol index entry")
        if entry["archive"] not in allowed_archives:
            raise RuntimeError(f"Unexpected archive in symbol index: {entry['archive']!r}")
        if entry["archive"] != core_archive:
            continue
        relative, source = _safe_pdb(artifact_dir / "debug-symbols", artifact_dir, entry.get("pdb_path"))
        key = relative.as_posix()
        if key in paths:
            previous = paths[key]
            identity = ("pdb_sha256", "rsds_guid", "rsds_age")
            if any(entry.get(field) != previous.get(field) for field in identity):
                raise RuntimeError(f"Conflicting indexed PDB identities for path: {key}")
        else:
            paths[key] = entry
            selected.append((entry, relative, source))
    if not selected:
        raise RuntimeError(f"Symbol index has no entries for core archive {core_archive!r}")

    destination.mkdir(parents=True, exist_ok=True)
    for _entry, relative, source in selected:
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    core_entries = [entry for entry in index["files"]
                    if isinstance(entry, dict) and entry.get("archive") == core_archive]
    core_index = {"schema_version": 1, "files": core_entries}
    (destination / "index.json").write_text(
        json.dumps(core_index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return core_index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path, help="Root of the downloaded Actions artifact")
    parser.add_argument("destination", type=Path, help="Directory for the core-only symbol set")
    parser.add_argument("core_archive", help="Exact PostgreSQL core archive basename")
    args = parser.parse_args()
    try:
        stage(args.artifact_dir, args.destination, args.core_archive)
    except RuntimeError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
