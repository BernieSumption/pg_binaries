#!/usr/bin/env python3
"""Verify Linux debug-symbol files against their index and finalized archives."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

from create_linux_symbols import sha256


def verify(index_path: Path, archives: list[Path]) -> dict:
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read symbol index {index_path}") from exc
    if (not isinstance(index, dict) or index.get("schema_version") != 1
            or not isinstance(index.get("files"), list) or not index["files"]):
        raise RuntimeError(f"Unsupported or empty symbol index: {index_path}")

    archives_by_name = {archive.name: archive for archive in archives}
    if len(archives_by_name) != len(archives):
        raise RuntimeError("Supplied archives must have unique basenames")
    digests = {name: sha256(path) for name, path in archives_by_name.items()}
    symbol_root = index_path.parent.resolve()
    seen_paths = set()

    for entry in index["files"]:
        if not isinstance(entry, dict):
            raise RuntimeError("Symbol index contains a malformed file entry")
        archive_name = entry.get("archive")
        if archive_name not in archives_by_name:
            raise RuntimeError(f"Archive missing for indexed symbol file: {archive_name}")
        if entry.get("archive_sha256") != digests[archive_name]:
            raise RuntimeError(f"Archive SHA-256 mismatch: {archive_name}")

        path_text = entry.get("debug_file_path")
        relative = PurePosixPath(path_text) if isinstance(path_text, str) else PurePosixPath()
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"Unsafe indexed debug-file path: {path_text!r}")
        debug_file = (symbol_root / Path(*relative.parts)).resolve()
        if not debug_file.is_relative_to(symbol_root):
            raise RuntimeError(f"Unsafe indexed debug-file path: {path_text!r}")
        if path_text in seen_paths:
            raise RuntimeError(f"Duplicate indexed debug-file path: {path_text}")
        seen_paths.add(path_text)
        if not debug_file.is_file():
            raise RuntimeError(f"Indexed debug file is missing: {path_text}")
        if sha256(debug_file) != entry.get("debug_file_sha256"):
            raise RuntimeError(f"Debug-file SHA-256 mismatch: {path_text}")

    if {entry["archive"] for entry in index["files"]} != set(archives_by_name):
        raise RuntimeError("Symbol index omits a supplied archive")

    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path, help="debug-symbols/index.json")
    parser.add_argument("archives", nargs="+", type=Path, help="exact finalized Linux archives")
    args = parser.parse_args()
    verify(args.index, args.archives)


if __name__ == "__main__":
    main()
