"""Download and safely extract selected files from a GitHub Actions artifact."""

import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile

MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_SIDECAR_BYTES = 4096


class BundleError(ValueError):
    pass


def download_and_extract_bundle(repository, artifact_id, digest_claim, artifact_paths,
                                output_directory, *, archive_paths=(),
                                max_total_bytes=MAX_ARCHIVE_BYTES):
    """Verify a GitHub ZIP digest, then extract an explicit file allowlist."""
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_directory) as temporary:
        zip_path = _download_verified_zip(repository, artifact_id, digest_claim, temporary)
        return extract_bundle(zip_path, artifact_paths, output_directory,
                              archive_paths=archive_paths, max_total_bytes=max_total_bytes)


def extract_bundle(zip_path, artifact_paths, output_directory, *, archive_paths=(),
                   max_total_bytes=MAX_ARCHIVE_BYTES):
    """Extract selected ZIP files and validate adjacent archive sidecars.

    Allowlist entries are relative POSIX paths. A basename lookup is permitted
    only when the requested path is absent and exactly one ZIP member has that
    basename. Archive paths require their adjacent ``.sha256`` member.
    """
    output_directory = Path(output_directory)
    requested = tuple(_safe_relative_path(path) for path in artifact_paths)
    archives = {_safe_relative_path(path) for path in archive_paths}
    if not requested or len(set(requested)) != len(requested):
        raise BundleError("artifact allowlist must contain unique paths")
    path_parts = [PurePosixPath(path).parts for path in requested]
    for index, parts in enumerate(path_parts):
        if any(parts == other[:len(parts)] or other == parts[:len(other)]
               for other in path_parts[index + 1:]):
            raise BundleError("artifact allowlist paths overlap")
    if not archives.issubset(requested):
        raise BundleError("archive paths must be present in the artifact allowlist")
    output_directory.mkdir(parents=True, exist_ok=True)
    destinations = {path: output_directory.joinpath(*PurePosixPath(path).parts)
                    for path in requested}
    if any(destination.exists() for destination in destinations.values()):
        raise BundleError("an artifact destination already exists")
    moved = []
    try:
        with tempfile.TemporaryDirectory(dir=output_directory.parent) as temporary:
            staging = Path(temporary)
            with zipfile.ZipFile(zip_path) as archive:
                members = archive.infolist()
                if len(members) > 1000:
                    raise BundleError("artifact ZIP contains too many entries")
                by_name = {}
                for item in members:
                    name = item.filename
                    if item.is_dir():
                        _safe_relative_path(name[:-1] if name.endswith("/") else name)
                        continue
                    safe_name = _safe_relative_path(name)
                    if safe_name in by_name:
                        raise BundleError("artifact ZIP contains duplicate paths")
                    by_name[safe_name] = item
                selected = {}
                used_members = set()
                for path in requested:
                    if path in by_name:
                        item = by_name[path]
                    else:
                        matches = [(name, item) for name, item in by_name.items()
                                   if PurePosixPath(name).name == PurePosixPath(path).name]
                        if len(matches) != 1:
                            raise BundleError("artifact path is absent or its basename is ambiguous")
                        item = matches[0][1]
                    if item.filename in used_members:
                        raise BundleError("multiple allowlist paths resolve to the same ZIP member")
                    used_members.add(item.filename)
                    selected[path] = item
                resolved = {path: item.filename for path, item in selected.items()}
                for archive_path in archives:
                    actual = resolved[archive_path]
                    sidecar_request = archive_path + ".sha256"
                    if sidecar_request not in selected:
                        raise BundleError("archive allowlist lacks its adjacent .sha256 sidecar")
                    if resolved[sidecar_request] != actual + ".sha256":
                        raise BundleError("archive and checksum sidecar are not adjacent")
                total = 0
                for item in selected.values():
                    if item.file_size > MAX_ARCHIVE_BYTES:
                        raise BundleError("artifact entry exceeds size limit")
                    total += item.file_size
                    if total > max_total_bytes:
                        raise BundleError("selected artifact entries exceed total size limit")
                staged_paths = {}
                for path, item in selected.items():
                    staged = staging.joinpath(*PurePosixPath(path).parts)
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    written = 0
                    with archive.open(item) as source, staged.open("wb") as target:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            written += len(chunk)
                            if written > MAX_ARCHIVE_BYTES or written > item.file_size:
                                raise BundleError("artifact entry exceeds declared size")
                            target.write(chunk)
                    if written != item.file_size:
                        raise BundleError("artifact entry size differs from ZIP metadata")
                    staged_paths[path] = staged
            for archive_path in archives:
                archive_digest = _sha256(staged_paths[archive_path])
                sidecar_path = staged_paths[archive_path + ".sha256"]
                if sidecar_path.stat().st_size > MAX_SIDECAR_BYTES:
                    raise BundleError("archive checksum sidecar exceeds size limit")
                try:
                    sidecar = sidecar_path.read_text(encoding="ascii").strip()
                except (UnicodeError, OSError) as exc:
                    raise BundleError("archive checksum sidecar is invalid") from exc
                basename = PurePosixPath(archive_path).name
                match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?" + re.escape(basename), sidecar)
                if not match or match.group(1).lower() != archive_digest:
                    raise BundleError("archive sidecar checksum is missing or does not match")
            for path in requested:
                destination = destinations[path]
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged_paths[path], destination)
                moved.append(destination)
        return destinations
    except Exception:
        for destination in moved:
            try:
                destination.unlink()
            except OSError:
                pass
        raise


def _download_verified_zip(repository, artifact_id, digest_claim, temporary):
    if (not isinstance(repository, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or any(part in {".", ".."} for part in repository.split("/"))):
        raise BundleError("GitHub repository identity is invalid")
    if not re.fullmatch(r"[1-9][0-9]*", str(artifact_id)):
        raise BundleError("GitHub artifact ID is invalid")
    if not isinstance(digest_claim, str) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest_claim):
        raise BundleError("GitHub artifact ZIP digest is invalid")
    zip_path = Path(temporary) / "artifact.zip"
    try:
        with zip_path.open("wb") as sink:
            result = subprocess.run(
                ["gh", "api", f"repos/{repository}/actions/artifacts/{artifact_id}/zip"],
                check=False, stdout=sink, stderr=subprocess.PIPE)
    except OSError as exc:
        raise BundleError(f"cannot run gh api: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise BundleError(f"gh api failed: {detail or result.returncode}")
    digest = hashlib.sha256()
    size = 0
    with zip_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            if size > MAX_ARCHIVE_BYTES:
                raise BundleError("artifact ZIP exceeds size limit")
            digest.update(chunk)
    if digest.hexdigest() != digest_claim.split(":", 1)[1].lower():
        raise BundleError("artifact ZIP digest differs from GitHub metadata")
    return zip_path


def _safe_relative_path(value):
    if not isinstance(value, str) or not value:
        raise BundleError("artifact path must be a non-empty relative path")
    path = PurePosixPath(value)
    if (path.is_absolute() or not path.parts or path == PurePosixPath(".") or value == "."
            or ".." in path.parts or "\\" in value
            or (path.parts and ":" in path.parts[0]) or path.as_posix() != value):
        raise BundleError("artifact path is unsafe")
    return value


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
