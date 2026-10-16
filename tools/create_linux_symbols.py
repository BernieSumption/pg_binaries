#!/usr/bin/env python3
"""Extract GNU debug files from the finalized Linux pilot archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path


BUILD_ID = re.compile(r"Build ID: ([0-9a-fA-F]+)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def module_member(name: str) -> bool:
    if name == "postgresql/bin/.pg-launcher":
        return True
    if name.startswith("postgresql/libexec/"):
        return True
    if name.startswith("postgresql/lib/") and not name.startswith((
        "postgresql/lib/runtime/", "postgresql/lib/glibc/"
    )):
        return True
    return name == "pgvector/lib/vector.so"


def build_id(path: Path) -> str:
    result = subprocess.run(
        ["readelf", "-n", str(path)], check=True, text=True, capture_output=True
    )
    match = BUILD_ID.search(result.stdout)
    if not match:
        raise RuntimeError(f"ELF file has no GNU build ID: {path}")
    return match.group(1).lower()


def has_dwarf(path: Path) -> bool:
    result = subprocess.run(
        ["readelf", "-SW", str(path)], check=True, text=True, capture_output=True
    )
    return ".debug_info" in result.stdout


def extract(archives: list[Path], output_dir: Path) -> dict:
    entries = []
    for archive in archives:
        archive_digest = sha256(archive)
        with tarfile.open(archive, "r:gz") as bundle, tempfile.TemporaryDirectory() as temp:
            temporary_root = Path(temp)
            for member in bundle.getmembers():
                if not (member.isfile() or member.islnk()) or not module_member(member.name):
                    continue
                source_stream = bundle.extractfile(member)
                if source_stream is None:
                    continue
                source = temporary_root / "module"
                with source.open("wb") as target:
                    target.write(source_stream.read())
                if source.read_bytes()[:4] != b"\x7fELF":
                    continue

                try:
                    module_id = build_id(source)
                except RuntimeError as exc:
                    raise RuntimeError(f"{archive.name}:{member.name}: {exc}") from exc
                relative_debug = Path(archive.name.removesuffix(".tar.gz")) / (member.name + ".debug")
                debug_file = output_dir / relative_debug
                debug_file.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["objcopy", "--only-keep-debug", str(source), str(debug_file)], check=True)
                debug_id = build_id(debug_file)
                if module_id != debug_id:
                    raise RuntimeError(
                        f"Build ID mismatch for {archive.name}:{member.name}: "
                        f"module {module_id}, debug file {debug_id}"
                    )
                if not has_dwarf(debug_file):
                    raise RuntimeError(f"No DWARF debug information for {archive.name}:{member.name}")
                entries.append({
                    "archive": archive.name,
                    "archive_sha256": archive_digest,
                    "module_path": member.name,
                    "module_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "gnu_build_id": module_id,
                    "debug_file_path": str(relative_debug),
                    "debug_file_sha256": sha256(debug_file),
                })

    if not entries:
        raise RuntimeError("No ELF modules found in the supplied archives")
    return {"schema_version": 1, "files": entries}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    index = extract(args.archives, args.output_dir)
    (args.output_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
