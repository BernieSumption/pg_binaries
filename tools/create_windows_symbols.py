#!/usr/bin/env python3
"""Index Windows PE modules in finalized archives against staged PDB files."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import tarfile
import tempfile
import uuid
from pathlib import Path, PurePosixPath


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _slice(data: bytes, offset: int, size: int, what: str) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise RuntimeError(f"Truncated {what}")
    return data[offset:offset + size]


def pe_codeview(path: Path) -> tuple[str, int] | None:
    """Return the PE CodeView RSDS GUID and age, or None for a non-PE file."""
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    pe_offset = _u32(data, 0x3c)
    if _slice(data, pe_offset, 4, "PE signature") != b"PE\0\0":
        return None
    coff = pe_offset + 4
    section_count = _u16(data, coff + 2)
    optional_size = _u16(data, coff + 16)
    optional = coff + 20
    magic = _u16(data, optional)
    if magic == 0x10b:
        directory_count_offset, directory_offset = 92, 96
    elif magic == 0x20b:
        directory_count_offset, directory_offset = 108, 112
    else:
        raise RuntimeError(f"Unsupported PE optional header in {path}")
    if optional_size < directory_offset:
        raise RuntimeError(f"Truncated PE optional header in {path}")
    directories = optional + directory_offset
    count = min(_u32(data, optional + directory_count_offset), (optional_size - directory_offset) // 8)
    debug_rva = debug_size = 0
    if count > 6:  # IMAGE_DIRECTORY_ENTRY_DEBUG
        debug_rva, debug_size = struct.unpack_from("<II", data, directories + 6 * 8)
    sections_offset = optional + optional_size
    sections = []
    for i in range(section_count):
        off = sections_offset + i * 40
        _slice(data, off, 40, "PE section header")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", data, off + 8)
        sections.append((virtual_address, max(virtual_size, raw_size), raw_offset, raw_size))

    def rva_offset(rva: int, size: int) -> int:
        for va, span, raw, raw_size in sections:
            if va <= rva and rva + size <= va + span and rva - va + size <= raw_size:
                return raw + rva - va
        raise RuntimeError(f"PE RVA 0x{rva:x} is outside file data in {path}")

    if not debug_rva or debug_size < 28:
        raise RuntimeError(f"PE file has no RSDS CodeView record: {path}")
    debug_offset = rva_offset(debug_rva, debug_size)
    for offset in range(debug_offset, debug_offset + debug_size, 28):
        _slice(data, offset, 28, "PE debug directory")
        _type, _timestamp, _major, _minor, kind, size, _address, raw = struct.unpack_from("<IIHHIIII", data, offset)
        if kind != 2:  # IMAGE_DEBUG_TYPE_CODEVIEW
            continue
        record = _slice(data, raw, size, "CodeView record")
        if record[:4] != b"RSDS":
            continue
        if len(record) < 24:
            raise RuntimeError(f"Truncated RSDS record in {path}")
        guid = uuid.UUID(bytes_le=record[4:20]).hex
        age = struct.unpack_from("<I", record, 20)[0]
        return (guid, age)
    raise RuntimeError(f"PE file has no RSDS CodeView record: {path}")


def pdb_identity(path: Path) -> tuple[str, int]:
    """Read the GUID and age from the PDB MSF 7.0 stream directory and Info stream."""
    data = path.read_bytes()
    magic = b"Microsoft C/C++ MSF 7.00\r\n\x1aDS\0\0\0"
    if data[:len(magic)] != magic:
        raise RuntimeError(f"Unsupported or invalid PDB MSF format: {path}")
    _slice(data, 0, 56, "PDB superblock")
    block_size, free_map, num_blocks, directory_size, _reserved, block_map = struct.unpack_from("<IIIIII", data, 32)
    if block_size < 512 or block_size & (block_size - 1) or num_blocks * block_size > len(data):
        raise RuntimeError(f"Invalid PDB block geometry: {path}")
    directory_blocks_count = (directory_size + block_size - 1) // block_size
    map_offset = block_map * block_size
    block_numbers = struct.unpack_from(f"<{directory_blocks_count}I", _slice(data, map_offset, directory_blocks_count * 4, "PDB directory block map"))
    directory = b"".join(_slice(data, block * block_size, block_size, "PDB stream directory") for block in block_numbers)[:directory_size]
    if len(directory) < 4:
        raise RuntimeError(f"Truncated PDB stream directory: {path}")
    stream_count = _u32(directory, 0)
    if stream_count > len(directory) // 4:
        raise RuntimeError(f"Invalid PDB stream count: {path}")
    sizes_offset = 4
    sizes = [_u32(directory, sizes_offset + 4 * i) for i in range(stream_count)]
    cursor = sizes_offset + stream_count * 4
    streams = []
    for size in sizes:
        if size == 0xffffffff:
            streams.append(None)
            continue
        count = (size + block_size - 1) // block_size
        block_ids = struct.unpack_from(f"<{count}I", _slice(directory, cursor, count * 4, "PDB stream block list")) if count else ()
        cursor += count * 4
        streams.append((size, block_ids))
    if len(streams) < 2 or streams[1] is None:
        raise RuntimeError(f"PDB has no Info stream: {path}")
    size, blocks = streams[1]
    info = b"".join(_slice(data, block * block_size, block_size, "PDB Info stream") for block in blocks)[:size]
    if len(info) < 28:
        raise RuntimeError(f"Truncated PDB Info stream: {path}")
    age = _u32(info, 8)
    guid = uuid.UUID(bytes_le=info[12:28]).hex
    return guid, age


def validate_members(bundle: tarfile.TarFile) -> None:
    for member in bundle.getmembers():
        path = PurePosixPath(member.name)
        if not member.name or path.is_absolute() or ".." in path.parts or "\\" in member.name:
            raise RuntimeError(f"Unsafe tar member path: {member.name!r}")
        if member.issym() or member.islnk():
            target = PurePosixPath(member.linkname)
            if target.is_absolute() or ".." in target.parts or "\\" in member.linkname:
                raise RuntimeError(f"Unsafe tar link: {member.name!r} -> {member.linkname!r}")


def module_member(name: str, external_runtime_dlls: set[str] | None = None) -> bool:
    parts = PurePosixPath(name).parts
    if not parts:
        return False
    if parts[0] == "pgvector":
        return len(parts) == 3 and parts[1] == "lib" and parts[2].lower().endswith(".dll")
    return (parts[0] == "postgresql" and len(parts) >= 3
            and parts[1] in {"bin", "lib", "libexec"}
            and parts[-1] not in (external_runtime_dlls or set())
            and parts[-1].lower().endswith((".exe", ".dll")))


def external_dlls(bundle: tarfile.TarFile) -> set[str]:
    name = "postgresql/manifest.json"
    if name not in bundle.getnames():
        return set()
    stream = bundle.extractfile(name)
    if stream is None:
        raise RuntimeError("Cannot read PostgreSQL package manifest")
    names = json.loads(stream.read()).get("bundled_runtime_dlls", [])
    if not isinstance(names, list) or any(not isinstance(item, str) for item in names):
        raise RuntimeError("Invalid bundled_runtime_dlls in PostgreSQL package manifest")
    return set(names)


def staged_pdbs(roots: list[Path]) -> dict[tuple[str, int], Path]:
    found = {}
    seen = set()
    for root in roots:
        for path in sorted(root.rglob("*.pdb")):
            if path in seen or not path.is_file() or path.is_symlink():
                continue
            seen.add(path)
            identity = pdb_identity(path)
            if identity in found:
                raise RuntimeError(f"Duplicate staged PDB identity {identity[0]} age {identity[1]}")
            found[identity] = path
    if not found:
        raise RuntimeError(f"No usable PDB files found under {', '.join(map(str, roots))}")
    return found


def extract(archives: list[Path], staged_dirs: list[Path], output_dir: Path) -> dict:
    by_id = staged_pdbs(staged_dirs)
    entries = []
    copied = {}
    with tempfile.TemporaryDirectory() as temp:
        module = Path(temp) / "module"
        for archive in archives:
            archive_digest = sha256(archive)
            with tarfile.open(archive, "r:gz") as bundle:
                validate_members(bundle)
                external_runtime_dlls = external_dlls(bundle)
                for member in bundle.getmembers():
                    if not member.isfile() or not module_member(member.name, external_runtime_dlls):
                        continue
                    stream = bundle.extractfile(member)
                    if stream is None:
                        continue
                    module.write_bytes(stream.read())
                    identity = pe_codeview(module)
                    if identity is None:
                        raise RuntimeError(f"Packaged module is not a PE image: {archive.name}:{member.name}")
                    pdb = by_id.get(identity)
                    if pdb is None:
                        raise RuntimeError(f"No staged PDB for {archive.name}:{member.name} RSDS {identity[0]} age {identity[1]}")
                    relative = Path("pdbs") / f"{identity[0]}-{identity[1]}" / pdb.name
                    destination = output_dir / relative
                    if pdb not in copied:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(pdb, destination)
                        copied[pdb] = (relative.as_posix(), sha256(destination))
                    pdb_path, pdb_digest = copied[pdb]
                    entries.append({"archive": archive.name, "archive_sha256": archive_digest,
                                    "module_path": member.name, "module_sha256": sha256(module),
                                    "rsds_guid": identity[0], "rsds_age": identity[1],
                                    "pdb_path": pdb_path, "pdb_sha256": pdb_digest})
    if not entries:
        raise RuntimeError("No PE modules with RSDS records found in the supplied archives")
    return {"schema_version": 1, "files": entries}


def verify(archives: list[Path], output_dir: Path) -> dict:
    index_path = output_dir / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read symbol index {index_path}") from exc
    if not isinstance(index, dict) or index.get("schema_version") != 1 or not isinstance(index.get("files"), list):
        raise RuntimeError(f"Unsupported or invalid symbol index: {index_path}")
    by_name = {archive.name: archive for archive in archives}
    digests = {name: sha256(path) for name, path in by_name.items()}
    checked, expected = set(), set()
    with tempfile.TemporaryDirectory() as temp:
        module = Path(temp) / "module"
        for archive in archives:
            with tarfile.open(archive, "r:gz") as bundle:
                validate_members(bundle)
                external_runtime_dlls = external_dlls(bundle)
                for member in bundle.getmembers():
                    if not member.isfile() or not module_member(member.name, external_runtime_dlls):
                        continue
                    stream = bundle.extractfile(member)
                    if stream is None:
                        continue
                    module.write_bytes(stream.read())
                    identity = pe_codeview(module)
                    if identity is None:
                        raise RuntimeError(f"Packaged module is not a PE image: {archive.name}:{member.name}")
                    expected.add((archive.name, member.name, identity[0], identity[1]))
        for entry in index["files"]:
            archive = by_name.get(entry.get("archive"))
            if archive is None:
                raise RuntimeError(f"Archive missing for indexed module: {entry.get('archive')}")
            if entry.get("archive_sha256") != digests[archive.name]:
                raise RuntimeError(f"Archive SHA-256 mismatch: {archive.name}")
            key = (archive.name, entry.get("module_path"), entry.get("rsds_guid"), entry.get("rsds_age"))
            with tarfile.open(archive, "r:gz") as bundle:
                member = next((m for m in bundle.getmembers() if m.name == entry.get("module_path") and m.isfile()), None)
                if member is None:
                    raise RuntimeError(f"Indexed archive member missing: {archive.name}:{entry.get('module_path')}")
                stream = bundle.extractfile(member)
                if stream is None:
                    raise RuntimeError(f"Cannot read archive member: {member.name}")
                module.write_bytes(stream.read())
            identity = pe_codeview(module)
            if identity != (entry.get("rsds_guid"), entry.get("rsds_age")):
                raise RuntimeError(f"Module RSDS mismatch: {archive.name}:{member.name}")
            if sha256(module) != entry.get("module_sha256"):
                raise RuntimeError(f"Module SHA-256 mismatch: {archive.name}:{member.name}")
            relative = PurePosixPath(entry.get("pdb_path", ""))
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise RuntimeError(f"Unsafe indexed PDB path: {entry.get('pdb_path')!r}")
            pdb = output_dir.joinpath(*relative.parts)
            if not pdb.is_file() or pdb.is_symlink() or not pdb.resolve().is_relative_to(output_dir.resolve()):
                raise RuntimeError(f"Indexed PDB is missing or unsafe: {pdb}")
            if sha256(pdb) != entry.get("pdb_sha256"):
                raise RuntimeError(f"PDB SHA-256 mismatch: {pdb}")
            if pdb_identity(pdb) != identity:
                raise RuntimeError(f"PDB GUID/age mismatch: {pdb}")
            checked.add(key)
    if not checked or checked != expected:
        raise RuntimeError(f"Symbol index coverage mismatch: missing={sorted(expected - checked)}, extra={sorted(checked - expected)}")
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--staged-pdbs", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify(args.archives, args.output_dir)
        return
    if args.staged_pdbs is None:
        parser.error("--staged-pdbs is required unless --verify-only is used")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    index = extract(args.archives, args.staged_pdbs, args.output_dir)
    (args.output_dir / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
