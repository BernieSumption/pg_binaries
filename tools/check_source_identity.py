#!/usr/bin/env python3
"""Check packaged PostgreSQL and pgvector source identities against selected pins."""

import argparse
import json
from pathlib import Path

from source_archive import source_archive


def check(root, platform, version, core_manifest, vector_metadata):
    archive_format = "tar.gz" if platform == "windows" else "tar.bz2"
    expected_core = source_archive("postgresql", version, archive_format, root)
    expected_vector = source_archive("pgvector", "0.8.7", "tar.gz", root)
    core = json.loads(Path(core_manifest).read_text(encoding="utf-8-sig"))
    vector = json.loads(Path(vector_metadata).read_text(encoding="utf-8-sig"))
    if core.get("source_archive") != expected_core:
        raise ValueError("PostgreSQL packaged source identity differs from selected archive")
    if vector.get("source_archive") != expected_vector:
        raise ValueError("pgvector packaged source identity differs from selected archive")
    if platform == "windows" and core.get("source_sha256") != expected_core["sha256"]:
        raise ValueError("PostgreSQL legacy source checksum differs from selected archive")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--platform", choices=("linux", "macos", "windows"), required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--core-manifest", type=Path, required=True)
    parser.add_argument("--vector-metadata", type=Path, required=True)
    args = parser.parse_args()
    check(args.root, args.platform, args.postgresql_version,
          args.core_manifest, args.vector_metadata)


if __name__ == "__main__":
    main()
