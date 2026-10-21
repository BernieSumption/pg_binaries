"""One-off tar.gz repack trial for central licence pointers."""

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import posixpath
import tarfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.license_pointer import LICENSE_POINTER


class RepackError(ValueError):
    pass


def _safe_name(name):
    if not name or name.startswith("/") or "\\" in name:
        raise RepackError(f"unsafe archive member path: {name!r}")
    parts = name.rstrip("/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise RepackError(f"unsafe archive member path: {name!r}")
    return "/".join(parts)


def _safe_link(member, canonical, names):
    if member.issym():
        if not member.linkname or member.linkname.startswith("/") or "\\" in member.linkname:
            raise RepackError(f"unsafe symlink target for {member.name!r}")
        target = posixpath.normpath(posixpath.join(posixpath.dirname(canonical), member.linkname))
        if target == ".." or target.startswith("../"):
            raise RepackError(f"symlink escapes archive root: {member.name!r}")
    elif member.islnk():
        target = _safe_name(member.linkname)
        if target not in names:
            raise RepackError(f"hardlink target is absent: {member.name!r} -> {member.linkname!r}")


def _read_members(path):
    try:
        archive = tarfile.open(path, "r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise RepackError(f"cannot read gzip tar archive: {path}") from exc
    with archive:
        members = archive.getmembers()
        canonical = {}
        for member in members:
            name = _safe_name(member.name)
            if name in canonical:
                raise RepackError(f"duplicate archive member: {name!r}")
            canonical[name] = member
            if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE,
                                   tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE,
                                   tarfile.CHRTYPE, tarfile.BLKTYPE):
                raise RepackError(f"unsupported tar member type: {member.name!r}")
        names = set(canonical)
        for name, member in canonical.items():
            _safe_link(member, name, names)
            parent = PurePosixPath(name).parent
            while str(parent) != ".":
                existing = canonical.get(str(parent))
                if existing and not existing.isdir():
                    raise RepackError(f"member has a non-directory parent: {name!r}")
                parent = parent.parent
        payloads = {}
        for name, member in canonical.items():
            if member.isfile():
                stream = archive.extractfile(member)
                if stream is None:
                    raise RepackError(f"cannot read regular member: {member.name!r}")
                payloads[name] = stream.read()
        return canonical, payloads


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _member_record(name, member, payloads):
    record = {
        "name": name,
        "type": member.type.decode("ascii", "replace"),
        "mode": member.mode,
        "size": member.size,
        "linkname": member.linkname,
        "uid": member.uid,
        "gid": member.gid,
        "uname": member.uname,
        "gname": member.gname,
        "mtime": member.mtime,
        "devmajor": member.devmajor,
        "devminor": member.devminor,
        "sparse": member.sparse,
        "pax_headers": member.pax_headers,
    }
    if name in payloads:
        record["sha256"] = _digest(payloads[name])
    return record


def _add_bytes(archive, name, data, mode, mtime):
    info = tarfile.TarInfo(name)
    info.type = tarfile.REGTYPE
    info.mode = mode
    info.size = len(data)
    info.mtime = mtime
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    archive.addfile(info, io.BytesIO(data))


def _add_directory(archive, name, mode, mtime):
    info = tarfile.TarInfo(name + "/")
    info.type = tarfile.DIRTYPE
    info.mode = mode
    info.size = 0
    info.mtime = mtime
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    archive.addfile(info)


def repack(source, component, output, report, remove):
    if (not component or component in (".", "..") or "/" in component
            or "\\" in component):
        raise RepackError(f"invalid component: {component!r}")
    source, output, report = Path(source), Path(output), Path(report)
    if (output.exists() or report.exists() or output.resolve() == source.resolve()
            or report.resolve() in (source.resolve(), output.resolve())):
        raise RepackError("output and report must be new paths distinct from the input")

    original, original_payloads = _read_members(source)
    expected_prefix = f"{component}/LICENSES/"
    remove_set = set()
    for requested in remove:
        name = _safe_name(requested)
        if not name.startswith(expected_prefix) or name == f"{component}/LICENSES/{component}/LICENCE":
            raise RepackError(f"removal must name a legacy member under {expected_prefix}: {name!r}")
        member = original.get(name)
        if member is None or not member.isfile():
            raise RepackError(f"removal must name an existing regular file: {name!r}")
        remove_set.add(name)
    for name, member in original.items():
        if member.islnk() and _safe_name(member.linkname) in remove_set:
            raise RepackError(f"cannot remove a hardlink target still used by {name!r}")

    pointer = f"{component}/LICENSES/{component}/LICENCE"
    if pointer in original:
        raise RepackError(f"refusing to overwrite existing pointer: {pointer}")
    pointer_dir = f"{component}/LICENSES/{component}"
    for name in (component, f"{component}/LICENSES"):
        member = original.get(name)
        if member is not None and not member.isdir():
            raise RepackError(f"pointer parent is not a directory: {name!r}")
    if pointer_dir in original and not original[pointer_dir].isdir():
        raise RepackError(f"pointer parent is not a directory: {pointer_dir!r}")

    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(source, "r:gz") as src, tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as dst:
            for member in src.getmembers():
                name = _safe_name(member.name)
                if name in remove_set:
                    continue
                info = copy.copy(member)
                info.pax_headers = dict(member.pax_headers)
                data = src.extractfile(member) if member.isfile() else None
                dst.addfile(info, data)
            if pointer_dir not in original:
                _add_directory(dst, pointer_dir, 0o755, int(original[component].mtime))
            _add_bytes(dst, pointer, LICENSE_POINTER.encode("utf-8"), 0o644,
                       int(original[component].mtime))
    except (OSError, tarfile.TarError) as exc:
        output.unlink(missing_ok=True)
        raise RepackError(f"cannot write output archive: {output}") from exc

    # Verify by reopening both archives independently before writing the report.
    verify_repack(source, output, component, remove_set)
    updated, updated_payloads = _read_members(output)
    diff = []
    for name in sorted(set(original) | set(updated)):
        if name in remove_set:
            status = "removed"
        elif name not in original:
            status = "added"
        else:
            status = "unchanged"
        entry = {"path": name, "status": status}
        if name in original:
            entry["before"] = _member_record(name, original[name], original_payloads)
        if name in updated:
            entry["after"] = _member_record(name, updated[name], updated_payloads)
        diff.append(entry)
    report_data = {
        "input": str(source), "input_sha256": _digest(source.read_bytes()),
        "output": str(output), "output_sha256": _digest(output.read_bytes()),
        "component": component, "removed": sorted(remove_set),
        "pointer": pointer, "pointer_sha256": _digest(LICENSE_POINTER.encode("utf-8")),
        "runtime_members_unchanged": True, "members": diff,
    }
    report.write_text(json.dumps(report_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_data


def verify_repack(source, output, component, remove_set):
    before, before_payloads = _read_members(source)
    after, after_payloads = _read_members(output)
    pointer = f"{component}/LICENSES/{component}/LICENCE"
    required_added = {pointer}
    pointer_dir = f"{component}/LICENSES/{component}"
    if pointer_dir not in before:
        required_added.add(pointer_dir)
    if set(after) != (set(before) - set(remove_set)) | required_added:
        raise RepackError("output member paths differ beyond explicit removals and pointer")
    for name in set(before) - set(remove_set):
        left, right = before[name], after[name]
        if _member_record(name, left, before_payloads) != _member_record(name, right, after_payloads):
            raise RepackError(f"retained archive member changed: {name!r}")
    if after_payloads.get(pointer) != LICENSE_POINTER.encode("utf-8"):
        raise RepackError("pointer contents differ from the required text")
    # All regular files in the retained payload, including executable libraries, are checked above.
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("component")
    parser.add_argument("output", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--remove", action="append", default=[], metavar="MEMBER",
                        help="exact legacy licence file path to remove; may be repeated")
    args = parser.parse_args()
    try:
        repack(args.input, args.component, args.output, args.report, args.remove)
    except RepackError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
