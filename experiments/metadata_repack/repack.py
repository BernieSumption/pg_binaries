"""One-off metadata-only patcher for the first-release archive defects."""

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile


class RepackError(ValueError):
    pass


FILENAME = re.compile(
    r"(?P<project>pgvector|hypopg|pg_jsonschema|postgis)-[^/]+-postgresql-"
    r"(?P<pg>\d+\.\d+)-(?P<platform>linux|windows|macos)-"
    r"(?P<arch>x86_64|arm64)\.tar\.gz"
)
CORE = re.compile(r"postgresql-(?P<pg>\d+\.\d+)-(?P<platform>linux|windows|macos)-(?P<arch>x86_64|arm64)\.tar\.gz")


def _identity(input_path, core_basename):
    match, core = FILENAME.fullmatch(Path(input_path).name), CORE.fullmatch(core_basename)
    if not match:
        raise RepackError("input basename is outside the known archive naming scheme")
    if not core:
        raise RepackError("core_archive.basename is not a supported PostgreSQL archive basename")
    if (match["pg"], match["platform"], match["arch"]) != (core["pg"], core["platform"], core["arch"]):
        raise RepackError("input filename and core_archive.basename identify different targets")
    project = match["project"]
    additions = {}
    if project == "pgvector":
        additions["postgresql_version"] = match["pg"]
    elif project == "hypopg" and match["platform"] == "windows":
        additions.update(configuration_prerequisites=[], runtime_prerequisites=[])
    elif project == "pg_jsonschema" and (
        match["platform"] == "windows" or (match["platform"], match["arch"]) == ("macos", "arm64")
    ):
        additions.update(configuration_prerequisites=[], runtime_prerequisites=[])
    elif project == "postgis" and match["platform"] == "windows":
        additions.update(configuration_prerequisites=[], runtime_prerequisites=[])
    else:
        raise RepackError("archive does not match one of the known metadata defects")
    return project, match["pg"], additions


def _members(path):
    try:
        with tarfile.open(path, "r:gz") as archive:
            entries = archive.getmembers()
            named = [m for m in entries if m.name.rstrip("/") == "metadata.json"]
            if len(named) != 1 or not named[0].isfile():
                raise RepackError("archive must contain exactly one root metadata.json regular file")
            payloads = {}
            for member in entries:
                if member.isfile():
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise RepackError(f"cannot read archive member {member.name!r}")
                    payloads[member.name] = stream.read()
            return entries, payloads
    except (OSError, tarfile.TarError) as exc:
        raise RepackError(f"cannot read gzip tar archive: {path}") from exc


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _record(member, payloads):
    result = (member.name, member.type, member.mode, member.linkname,
              member.uid, member.gid, member.uname, member.gname, member.mtime,
              member.devmajor, member.devminor, member.sparse, member.pax_headers)
    if member.isfile():
        result += (member.size, _digest(payloads[member.name]))
    return result


def verify_repack(source, output, expected_metadata):
    before, before_data = _members(source)
    after, after_data = _members(output)
    before_by_name = {m.name: m for m in before}
    after_by_name = {m.name: m for m in after}
    if len(before_by_name) != len(before) or len(after_by_name) != len(after):
        raise RepackError("duplicate archive member paths are not supported")
    if set(before_by_name) != set(after_by_name):
        raise RepackError("archive member paths changed")
    for name in before_by_name:
        if name != "metadata.json" and _record(before_by_name[name], before_data) != _record(after_by_name[name], after_data):
            raise RepackError(f"non-metadata archive member changed: {name!r}")
    if _record(before_by_name["metadata.json"], before_data)[:-2] != _record(after_by_name["metadata.json"], after_data)[:-2]:
        raise RepackError("metadata member attributes beyond size changed")
    try:
        original = json.loads(before_data["metadata.json"])
        actual = json.loads(after_data["metadata.json"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise RepackError("archive metadata.json is invalid") from exc
    if not isinstance(original, dict) or not isinstance(actual, dict):
        raise RepackError("archive metadata.json must be an object")
    expected = dict(original)
    expected.update(expected_metadata)
    if actual != expected:
        raise RepackError("output metadata differs beyond expected additions")
    if before_data["metadata.json"] == after_data["metadata.json"]:
        raise RepackError("metadata content did not change")
    return True


def repack(source, core_basename, output):
    source, output = Path(source), Path(output)
    if output.exists() or output.resolve() == source.resolve():
        raise RepackError("output must be a new path distinct from input")
    project, pg, additions = _identity(source, core_basename)
    members, payloads = _members(source)
    try:
        metadata = json.loads(payloads["metadata.json"])
    except json.JSONDecodeError as exc:
        raise RepackError("input metadata.json is invalid") from exc
    if not isinstance(metadata, dict) or metadata.get("project") != project:
        raise RepackError("metadata project does not match the archive filename")
    if metadata.get("postgresql_version", pg) != pg:
        raise RepackError("existing postgresql_version conflicts with filename and core archive")
    for field, expected in additions.items():
        if field in metadata and metadata[field] != expected:
            raise RepackError(f"existing {field} conflicts with the known metadata addition")
    for field, expected in additions.items():
        metadata[field] = expected
    metadata_bytes = (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(source, "r:gz") as src, tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as dst:
            for original in members:
                info = copy.copy(original)
                info.pax_headers = dict(original.pax_headers)
                data = io.BytesIO(metadata_bytes) if original.name.rstrip("/") == "metadata.json" else (
                    src.extractfile(original) if original.isfile() else None
                )
                if original.name.rstrip("/") == "metadata.json":
                    info.size = len(metadata_bytes)
                dst.addfile(info, data)
    except (OSError, tarfile.TarError) as exc:
        output.unlink(missing_ok=True)
        raise RepackError(f"cannot write output archive: {output}") from exc
    verify_repack(source, output, additions)
    return {"project": project, "postgresql_version": pg, "added": additions,
            "input_sha256": _digest(source.read_bytes()), "output_sha256": _digest(output.read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("core_archive_basename", help="metadata core_archive.basename value")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(repack(args.input, args.core_archive_basename, args.output), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, RepackError) as exc:
        raise SystemExit(str(exc))
