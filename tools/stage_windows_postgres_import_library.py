#!/usr/bin/env python3
"""Stage PostgreSQL's Meson import library under pgvector's Windows filename."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_import_library(library_directory):
    directory = Path(library_directory)
    source = directory / "postgres.exe.lib"
    target = directory / "postgres.lib"
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"Meson PostgreSQL import library is missing or not a regular file: {source}")
    if target.exists() or target.is_symlink() or os.path.lexists(target):
        raise ValueError(f"refusing to overwrite existing PostgreSQL import library alias: {target}")
    expected = sha256(source)
    shutil.copyfile(source, target)
    if not target.is_file() or sha256(target) != expected:
        target.unlink(missing_ok=True)
        raise ValueError("staged PostgreSQL import library differs from Meson's generated file")
    return target


def verify_import_library(library_directory, manifest_path):
    directory = Path(library_directory)
    source = directory / "postgres.exe.lib"
    target = directory / "postgres.lib"
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    identity = manifest.get("windows_import_library")
    if not isinstance(identity, dict) or identity.get("filename") != "postgres.lib" or identity.get("alias_of") != "postgres.exe.lib":
        raise ValueError("PostgreSQL manifest does not declare the expected Windows import-library alias")
    for path in (source, target):
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"required PostgreSQL import library is missing or not a regular file: {path}")
    source_hash = sha256(source)
    if sha256(target) != source_hash or identity.get("sha256") != source_hash:
        raise ValueError("packaged PostgreSQL import-library alias differs from Meson's generated file")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-directory", type=Path, required=True)
    parser.add_argument("--verify-manifest", type=Path)
    args = parser.parse_args()
    if args.verify_manifest:
        print(verify_import_library(args.library_directory, args.verify_manifest))
    else:
        print(stage_import_library(args.library_directory))


if __name__ == "__main__":
    main()
