#!/usr/bin/env python3
"""Validate exact core and pinned source archives for the Linux pgvector trial."""
import hashlib, json, re, sys, tarfile
from pathlib import Path

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def validate_source(path, expected, version="0.8.7"):
    path = Path(path)
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", version):
        raise ValueError("pgvector version must be a dotted numeric release")
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or sha256(path) != expected:
        raise ValueError("pgvector source archive does not match checked support.json SHA-256")
    with tarfile.open(path, "r:gz") as archive:
        roots = {member.name.split("/", 1)[0] for member in archive.getmembers() if member.name}
    if roots != {f"pgvector-{version}"}:
        raise ValueError(f"source archive does not contain pgvector-{version} root")

def validate_core(path, sidecar, expected_sha, version, architecture, expected_source_sha):
    path = Path(path)
    expected_name = f"postgresql-{version}-linux-{architecture}.tar.gz"
    if (path.name != expected_name or not re.fullmatch(r"(15|16|17|18)\.[0-9]+", version)
            or architecture not in {"x86_64", "arm64"}):
        raise ValueError(f"selected path requires PostgreSQL 15 through 18 on x86_64 or arm64: {expected_name}")
    fields = Path(sidecar).read_text(encoding="utf-8").split()
    if len(fields) < 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]) or fields[-1] != path.name:
        raise ValueError("core checksum sidecar must identify supplied archive basename")
    actual = sha256(path)
    if actual.lower() != fields[0].lower():
        raise ValueError("core archive checksum does not match sidecar")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha) or actual.lower() != expected_sha.lower():
        raise ValueError("core archive checksum does not match separately supplied expected SHA-256")
    with tarfile.open(path, "r:gz") as archive:
        member = archive.extractfile("postgresql/manifest.json")
        if member is None:
            raise ValueError("core archive has no postgresql/manifest.json")
        manifest = json.load(member)
    if (manifest.get("component"), manifest.get("version"), manifest.get("platform"),
        manifest.get("architecture")) != ("postgresql", version, "linux", architecture):
        raise ValueError("core manifest identity does not match trial")
    source = manifest.get("source_archive")
    if (not re.fullmatch(r"[0-9a-f]{64}", expected_source_sha)
            or not isinstance(source, dict)
            or source.get("sha256") != expected_source_sha):
        raise ValueError("core source archive does not match the selected PostgreSQL release")
    return actual

def main(argv):
    command, *args = argv[1:]
    if command == "validate-source": validate_source(*args)
    elif command == "validate-core": validate_core(*args)
    else: raise ValueError("expected validate-core or validate-source")

if __name__ == "__main__":
    try: main(sys.argv)
    except (OSError, ValueError, KeyError, tarfile.TarError, json.JSONDecodeError) as error:
        raise SystemExit(str(error))
