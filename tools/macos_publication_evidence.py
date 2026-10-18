"""Low-level checksum and evidence retention helpers for macOS publication paths."""

import hashlib
import json
from pathlib import Path
import re
import shutil

import coverage

MAX_EVIDENCE_BYTES = 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_sidecar(archive, digest, missing_message):
    archive = Path(archive)
    sidecar = archive.with_name(archive.name + ".sha256")
    try:
        lines = sidecar.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise coverage.CoverageError(missing_message.format(name=archive.name)) from exc
    if (len(lines) != 1
            or not re.fullmatch(rf"[0-9a-fA-F]{{64}}\s+\*?{re.escape(archive.name)}", lines[0])
            or lines[0].split()[0].lower() != digest):
        raise coverage.CoverageError(f"checksum sidecar does not match {archive.name}")


def read_json_object(path, max_bytes=MAX_EVIDENCE_BYTES):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise coverage.CoverageError(
            f"evidence must be a regular file of at most {max_bytes} bytes: {path}")
    value = coverage.load_json(path)
    if not isinstance(value, dict):
        raise coverage.CoverageError(f"{path}: expected JSON object")
    return value


def retain(source, destination, copies, max_bytes=MAX_EVIDENCE_BYTES):
    source, destination = Path(source), Path(destination)
    _validate_file(source, max_bytes, "no larger than")
    if destination.exists() and destination.read_bytes() != source.read_bytes():
        raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
    copies.append((source, destination))


def copy_retained(copies, max_bytes=MAX_EVIDENCE_BYTES):
    pending = {}
    for source, destination in copies:
        source, destination = Path(source), Path(destination)
        _validate_file(source, max_bytes)
        content = source.read_bytes()
        if ((destination in pending and pending[destination] != content)
                or (destination.exists() and destination.read_bytes() != content)):
            raise coverage.CoverageError(f"refusing to replace retained evidence {destination}")
        pending[destination] = content
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)


def _validate_file(path, max_bytes, size_phrase="at most"):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise coverage.CoverageError(
            f"evidence must be a regular file {size_phrase} {max_bytes} bytes: {path}")
