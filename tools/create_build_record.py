#!/usr/bin/env python3
"""Create a durable provenance record for finalized PostgreSQL and pgvector archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path


PROVENANCE_FIELDS = ("build_id", "source_revision", "build_configuration", "platform", "architecture")
OPTIONAL_PROVENANCE_FIELDS = ("builder_image_id",)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def archive_json(archive: Path, member_name: str) -> dict:
    try:
        with tarfile.open(archive, "r:*") as tf:
            matches = [member for member in tf.getmembers()
                       if Path(member.name).name == member_name and member.isfile()]
            if len(matches) != 1:
                raise ValueError(f"{archive} must contain exactly one {member_name}")
            stream = tf.extractfile(matches[0])
            if stream is None:
                raise ValueError(f"cannot read {member_name} from {archive}")
            value = json.loads(stream.read().decode("utf-8-sig"))
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {member_name} from {archive}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{member_name} in {archive} must be a JSON object")
    return value


def create_record(postgresql: Path, pgvector: Path, symbols: Path | None = None) -> dict:
    core = archive_json(postgresql, "manifest.json")
    vector = archive_json(pgvector, "metadata.json")
    for field in PROVENANCE_FIELDS:
        if not isinstance(core.get(field), str) or not core[field]:
            raise ValueError(f"PostgreSQL manifest has no valid {field}")
        if core[field] != vector.get(field):
            raise ValueError(f"PostgreSQL and pgvector {field} values differ")
    for field in OPTIONAL_PROVENANCE_FIELDS:
        if field in core or field in vector:
            if not isinstance(core.get(field), str) or not core[field]:
                raise ValueError(f"PostgreSQL manifest has no valid {field}")
            if core[field] != vector.get(field):
                raise ValueError(f"PostgreSQL and pgvector {field} values differ")
    if not postgresql.is_file() or not pgvector.is_file():
        raise ValueError("both package archives must be files")

    identity = {field: core[field] for field in PROVENANCE_FIELDS}
    identity.update({field: core[field] for field in OPTIONAL_PROVENANCE_FIELDS if field in core})
    record = {
        "schema_version": 1,
        "record_id": f"{core['build_id']}-{core['platform']}-{core['architecture']}",
        **identity,
        "packages": {
            "postgresql": {"archive": postgresql.name, "sha256": sha256(postgresql)},
            "pgvector": {"archive": pgvector.name, "sha256": sha256(pgvector)},
        },
    }
    if symbols is not None:
        if not symbols.is_file():
            raise ValueError(f"symbol index does not exist: {symbols}")
        index = json.loads(symbols.read_text(encoding="utf-8-sig"))
        files = index.get("files") if isinstance(index, dict) else None
        if not isinstance(files, list) or not files:
            raise ValueError("symbol index must contain files")
        package_hashes = {entry["archive"]: entry["sha256"] for entry in record["packages"].values()}
        represented = set()
        for entry in files:
            if not isinstance(entry, dict) or entry.get("archive") not in package_hashes:
                raise ValueError("symbol index references an unknown archive")
            archive_name = entry["archive"]
            if entry.get("archive_sha256") != package_hashes[archive_name]:
                raise ValueError("symbol index archive checksum differs from package")
            represented.add(archive_name)
        if represented != set(package_hashes):
            raise ValueError("symbol index omits a package archive")
        record["symbol_index"] = {"path": symbols.name, "sha256": sha256(symbols)}
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("postgresql", type=Path, help="final PostgreSQL tar archive")
    parser.add_argument("pgvector", type=Path, help="final pgvector tar archive")
    parser.add_argument("--symbols", type=Path, help="optional symbol-index file")
    parser.add_argument("--output", type=Path, required=True, help="JSON record output path")
    args = parser.parse_args()
    record = create_record(args.postgresql, args.pgvector, args.symbols)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
