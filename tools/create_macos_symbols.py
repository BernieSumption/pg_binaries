#!/usr/bin/env python3
"""Match finalized macOS archive binaries to staged dSYM bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


UUID_LINE = re.compile(r"UUID: ([0-9A-Fa-f-]+) \(([^)]+)\)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def validate_members(bundle: tarfile.TarFile) -> None:
    for member in bundle.getmembers():
        name = member.name
        path = PurePosixPath(name)
        if not name or path.is_absolute() or ".." in path.parts or "\\" in name:
            raise RuntimeError(f"Unsafe tar member path: {name!r}")
        if member.issym() or member.islnk():
            target = PurePosixPath(member.linkname)
            if target.is_absolute() or ".." in target.parts or "\\" in member.linkname:
                raise RuntimeError(f"Unsafe tar link: {name!r} -> {member.linkname!r}")


def module_member(name: str, bundled_dependencies: set[str]) -> bool:
    parts = PurePosixPath(name).parts
    if not parts:
        return False
    if parts[0] == "pgvector":
        return len(parts) == 3 and parts[1] == "lib" and parts[2] == "vector.dylib"
    if parts[0] != "postgresql" or len(parts) < 3:
        return False
    return (parts[1] in {"bin", "lib", "libexec"}
            and parts[-1] not in bundled_dependencies and not parts[-1].endswith(".a"))


def uuids(path: Path) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["xcrun", "dwarfdump", "--uuid", str(path)], check=True,
        text=True, capture_output=True,
    )
    return [(match.group(1).lower(), match.group(2)) for match in UUID_LINE.finditer(result.stdout)]


def has_dwarf(path: Path) -> bool:
    result = subprocess.run(
        ["xcrun", "dwarfdump", "--debug-info", str(path)], check=True,
        text=True, capture_output=True,
    )
    return "DW_TAG_" in result.stdout or "Compile Unit:" in result.stdout


def staged_dsyms(root: Path) -> dict[str, tuple[Path, Path]]:
    found: dict[str, tuple[Path, Path]] = {}
    for bundle in sorted(root.rglob("*.dSYM")):
        if not bundle.is_dir() or bundle.is_symlink():
            continue
        dwarf_dir = bundle / "Contents/Resources/DWARF"
        for dwarf in sorted(dwarf_dir.iterdir()) if dwarf_dir.is_dir() else []:
            if not dwarf.is_file() or dwarf.is_symlink():
                continue
            for uuid, _arch in uuids(dwarf):
                if uuid in found:
                    raise RuntimeError(f"Duplicate staged dSYM UUID {uuid}: {found[uuid][0]} and {bundle}")
                found[uuid] = (bundle, bundle.relative_to(root))
    return found


def extract(archives: list[Path], staged_dir: Path, output_dir: Path) -> dict:
    by_uuid = staged_dsyms(staged_dir)
    if not by_uuid:
        raise RuntimeError(f"No usable dSYM UUIDs found under {staged_dir}")
    copied: dict[Path, tuple[str, str]] = {}
    entries = []
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp) / "module"
        for archive in archives:
            archive_digest = sha256(archive)
            with tarfile.open(archive, "r:gz") as bundle:
                validate_members(bundle)
                dependency_member = "postgresql/bundled-dependencies.json"
                bundled_dependencies: set[str] = set()
                dependency_file = bundle.extractfile(dependency_member) if dependency_member in bundle.getnames() else None
                if dependency_file is not None:
                    try:
                        bundled_dependencies = set(json.loads(dependency_file.read()))
                    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                        raise RuntimeError(f"Invalid bundled-dependencies.json in {archive.name}") from exc
                for member in bundle.getmembers():
                    if not member.isfile() or not module_member(member.name, bundled_dependencies):
                        continue
                    stream = bundle.extractfile(member)
                    if stream is None:
                        continue
                    source.write_bytes(stream.read())
                    try:
                        module_uuids = uuids(source)
                    except subprocess.CalledProcessError:
                        continue
                    if not module_uuids:
                        continue
                    module_digest = sha256(source)
                    for uuid, architecture in module_uuids:
                        staged = by_uuid.get(uuid)
                        if staged is None:
                            raise RuntimeError(f"No staged dSYM for {archive.name}:{member.name} UUID {uuid}")
                        dsym, staged_relative = staged
                        dwarf_files = list((dsym / "Contents/Resources/DWARF").iterdir())
                        dwarf_files = [p for p in dwarf_files if p.is_file() and not p.is_symlink()]
                        if not any(has_dwarf(path) for path in dwarf_files):
                            raise RuntimeError(f"No useful DWARF information in {dsym}")
                        relative_dsym = Path("dSYMs") / staged_relative
                        destination = output_dir / relative_dsym
                        if dsym not in copied:
                            if destination.exists():
                                shutil.rmtree(destination)
                            shutil.copytree(dsym, destination, symlinks=False)
                            copied[dsym] = (str(relative_dsym), tree_sha256(destination))
                        dsym_path, dsym_digest = copied[dsym]
                        entries.append({
                            "archive": archive.name,
                            "archive_sha256": archive_digest,
                            "module_path": member.name,
                            "module_sha256": module_digest,
                            "uuid": uuid,
                            "architecture": architecture,
                            "dsym_path": dsym_path,
                            "dsym_sha256": dsym_digest,
                        })
    if not entries:
        raise RuntimeError("No Mach-O modules found in the supplied archives")
    return {"schema_version": 1, "files": entries}


def verify(archives: list[Path], output_dir: Path) -> dict:
    index_path = output_dir / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read symbol index {index_path}") from exc
    if not isinstance(index, dict) or index.get("schema_version") != 1 or not isinstance(index.get("files"), list):
        raise RuntimeError(f"Unsupported or invalid symbol index: {index_path}")
    archives_by_name = {archive.name: archive for archive in archives}
    hashes = {name: sha256(path) for name, path in archives_by_name.items()}
    checked = set()
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp) / "module"
        for entry in index["files"]:
            archive_name = entry.get("archive")
            archive = archives_by_name.get(archive_name)
            if archive is None:
                raise RuntimeError(f"Archive missing for indexed module: {archive_name}")
            if hashes[archive_name] != entry.get("archive_sha256"):
                raise RuntimeError(f"Archive SHA-256 mismatch: {archive_name}")
            with tarfile.open(archive, "r:gz") as bundle:
                validate_members(bundle)
                member = next((m for m in bundle.getmembers()
                               if m.name == entry.get("module_path") and m.isfile()), None)
                if member is None:
                    raise RuntimeError(f"Indexed archive member missing: {archive_name}:{entry.get('module_path')}")
                stream = bundle.extractfile(member)
                if stream is None:
                    raise RuntimeError(f"Cannot read archive member: {archive_name}:{member.name}")
                source.write_bytes(stream.read())
            if sha256(source) != entry.get("module_sha256"):
                raise RuntimeError(f"Module SHA-256 mismatch: {archive_name}:{member.name}")
            module_uuids = uuids(source)
            if (entry.get("uuid"), entry.get("architecture")) not in module_uuids:
                raise RuntimeError(f"Module UUID mismatch: {archive_name}:{member.name}")

            relative = PurePosixPath(entry.get("dsym_path", ""))
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise RuntimeError(f"Unsafe indexed dSYM path: {entry.get('dsym_path')!r}")
            dsym = output_dir.joinpath(*relative.parts)
            if not dsym.is_dir() or dsym.is_symlink() or not dsym.resolve().is_relative_to(output_dir.resolve()):
                raise RuntimeError(f"Indexed dSYM is missing or unsafe: {dsym}")
            if any(path.is_symlink() for path in dsym.rglob("*")):
                raise RuntimeError(f"Indexed dSYM contains a symbolic link: {dsym}")
            if tree_sha256(dsym) != entry.get("dsym_sha256"):
                raise RuntimeError(f"dSYM SHA-256 mismatch: {dsym}")
            dwarf_dir = dsym / "Contents/Resources/DWARF"
            dwarf_files = [p for p in dwarf_dir.iterdir() if p.is_file() and not p.is_symlink()] if dwarf_dir.is_dir() else []
            dsyms = [pair for dwarf in dwarf_files for pair in uuids(dwarf)]
            if (entry.get("uuid"), entry.get("architecture")) not in dsyms:
                raise RuntimeError(f"dSYM UUID mismatch: {dsym}")
            if not any(has_dwarf(path) for path in dwarf_files):
                raise RuntimeError(f"No useful DWARF information in {dsym}")
            checked.add((archive_name, member.name, entry["uuid"], entry["architecture"]))
        expected = set()
        for archive in archives:
            with tarfile.open(archive, "r:gz") as bundle:
                validate_members(bundle)
                dependency_name = "postgresql/bundled-dependencies.json"
                dependency_file = bundle.extractfile(dependency_name) if dependency_name in bundle.getnames() else None
                bundled_dependencies = set(json.loads(dependency_file.read())) if dependency_file else set()
                for member in bundle.getmembers():
                    if not member.isfile() or not module_member(member.name, bundled_dependencies):
                        continue
                    stream = bundle.extractfile(member)
                    if stream is None:
                        continue
                    source.write_bytes(stream.read())
                    try:
                        module_uuids = uuids(source)
                    except subprocess.CalledProcessError:
                        continue
                    expected.update((archive.name, member.name, uuid, architecture)
                                    for uuid, architecture in module_uuids)
    if not checked or checked != expected:
        raise RuntimeError(f"Symbol index coverage mismatch: missing={sorted(expected - checked)}, extra={sorted(checked - expected)}")
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--staged-dsyms", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify(args.archives, args.output_dir)
        return
    if args.staged_dsyms is None:
        parser.error("--staged-dsyms is required unless --verify-only is used")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    index = extract(args.archives, args.staged_dsyms, args.output_dir)
    (args.output_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
