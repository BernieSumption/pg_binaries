"""Prepare checksum-verified source trees without changing cached archives."""

import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(source, cache):
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / source["sha256"]
    if archive.is_file() and sha256(archive) == source["sha256"]:
        return archive
    descriptor, temporary = tempfile.mkstemp(dir=cache, prefix="download-")
    os.close(descriptor)
    temporary = Path(temporary)
    try:
        subprocess.run(["curl", "--fail", "--location", "--retry", "3", "--silent", "--show-error",
                        source["url"], "--output", str(temporary)], check=True)
        if sha256(temporary) != source["sha256"]:
            raise ValueError(f"source checksum mismatch: {source['url']}")
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    return archive


def extract(archive, destination):
    destination.mkdir(parents=True, exist_ok=False)
    root = destination.resolve()
    try:
        with tarfile.open(archive, "r:*") as tar:
            members = tar.getmembers()
            for member in members:
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                    raise ValueError(f"unsafe source archive entry: {member.name}")
                if member.issym() or member.islnk():
                    link = PurePosixPath(member.linkname)
                    target = root / (path.parent if member.issym() else PurePosixPath()) / link
                    if link.is_absolute() or not _inside(target.resolve(), root):
                        raise ValueError(f"unsafe source archive link: {member.name}")
            # Check again while extracting: an earlier symlink can change a later path.
            for member in members:
                if not _inside((root / member.name).resolve(), root):
                    raise ValueError(f"source archive path escapes destination: {member.name}")
                tar.extract(member, root)
        entries = list(destination.iterdir())
        if len(entries) == 1 and entries[0].is_dir() and not entries[0].is_symlink():
            enclosing = entries[0]
            with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
                contents = Path(temporary) / "contents"
                enclosing.rename(contents)
                for child in contents.iterdir():
                    child.rename(destination / child.name)
        for directory, directories, files in os.walk(destination, followlinks=False):
            for name in directories + files:
                path = Path(directory) / name
                if path.is_symlink() and not _inside(path.resolve(), root):
                    raise ValueError(f"source link escapes normalised tree: {path}")
    except Exception:
        shutil.rmtree(destination)
        raise


def _inside(path, root):
    return path == root or root in path.parents


def prepare_sources(sources, destination, cache):
    destination.mkdir(parents=True, exist_ok=True)
    for source_id, source in sources.items():
        extract(download(source, cache), destination / source_id)
