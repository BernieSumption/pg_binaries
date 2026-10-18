#!/usr/bin/env python3
"""Create a temporary Windows core identity from a checked PostgreSQL archive."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import tempfile

from windows_core_pin import PG_VERSIONS, REQUIRED

MAX_MANIFEST_SIZE = 1024 * 1024
MAX_MEMBERS = 100_000


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json_file(path, label):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read {label}: {exc}") from exc


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest(archive_path):
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            if len(members) > MAX_MEMBERS:
                raise ValueError("core archive has too many entries")
            found = []
            names = set()
            for member in members:
                if member.name in names:
                    raise ValueError("core archive contains duplicate paths")
                names.add(member.name)
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or "\\" in member.name:
                    raise ValueError("core archive contains an unsafe path")
                if member.name == "postgresql/manifest.json":
                    if not member.isfile() or member.size > MAX_MANIFEST_SIZE:
                        raise ValueError("core archive manifest is not a bounded regular file")
                    found.append(member)
            if len(found) != 1:
                raise ValueError("core archive must contain exactly one manifest")
            stream = archive.extractfile(found[0])
            if stream is None:
                raise ValueError("cannot read core archive manifest")
            raw = stream.read(MAX_MANIFEST_SIZE + 1)
            if len(raw) > MAX_MANIFEST_SIZE:
                raise ValueError("core archive manifest exceeds size limit")
            return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot inspect core archive: {exc}") from exc


def create_target(base_path, archive_path, source_run_id, output_path, source_run_attempt="1",
                  source_artifact_name=None):
    base_path, archive_path, output_path = map(Path, (base_path, archive_path, output_path))
    if not isinstance(source_run_id, str) or not re.fullmatch(r"[1-9][0-9]*", source_run_id):
        raise ValueError("source run ID must be a positive decimal integer")
    if not isinstance(source_run_attempt, str) or not re.fullmatch(r"[1-9][0-9]*", source_run_attempt):
        raise ValueError("source run attempt must be a positive integer")
    if (source_artifact_name is not None and
            (not isinstance(source_artifact_name, str) or
             not re.fullmatch(r"[A-Za-z0-9_.-]+", source_artifact_name))):
        raise ValueError("source artifact name must be a safe filename")
    target = _json_file(base_path, "base Windows core pin")
    if not isinstance(target, dict) or set(target) != REQUIRED:
        raise ValueError("base Windows core pin has missing or unexpected fields")
    version = target.get("postgresql_version")
    if (version not in PG_VERSIONS or target.get("platform") != "windows-x86_64"
            or target.get("architecture") != "x86_64"):
        raise ValueError("base Windows core pin has an unsupported target")
    expected_name = f"postgresql-{version}-windows-x86_64.tar.gz"
    if target.get("archive_name") != expected_name or archive_path.name != expected_name:
        raise ValueError("core archive name does not match target")
    sidecar = Path(str(archive_path) + ".sha256")
    try:
        sidecar_text = sidecar.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read SHA-256 sidecar: {exc}") from exc
    match = re.fullmatch(r"([0-9a-f]{64})(?:\s+\*?([^\s]+))?", sidecar_text)
    if not match or (match.group(2) is not None and match.group(2) != archive_path.name):
        raise ValueError("SHA-256 sidecar is malformed or names a different archive")
    digest = _sha256(archive_path)
    if digest != match.group(1):
        raise ValueError("core archive checksum differs from its sidecar")
    manifest = _manifest(archive_path)
    build_id = f"github-{source_run_id}-{source_run_attempt}"
    expected = {"component": "postgresql", "version": version,
                "postgresql_version": version, "platform": "windows",
                "architecture": "x86_64", "build_id": build_id}
    if not isinstance(manifest, dict) or any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("core archive manifest does not match target and source run")
    revision = manifest.get("source_revision")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("core archive manifest has an invalid source revision")
    target.update({"run_id": source_run_id, "build_id": build_id,
                   "source_revision": revision, "sha256": digest})
    if source_artifact_name is not None:
        target["artifact_name"] = source_artifact_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output_path.name}.", dir=output_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(target, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, output_path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-pin", type=Path, required=True)
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-run-attempt", default="1")
    parser.add_argument("--source-artifact-name")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        create_target(args.base_pin, args.core_archive, args.source_run_id, args.output,
                      args.source_run_attempt, args.source_artifact_name)
        print(f"Wrote temporary Windows core identity: {args.output}")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"Windows core target config: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
