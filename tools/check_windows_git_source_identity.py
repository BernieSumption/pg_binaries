#!/usr/bin/env python3
"""Validate Windows PostgreSQL Git-checkout provenance and pgvector archive identity."""

import argparse
import json
from pathlib import Path

from postgresql_git_source import source_checkout
from source_archive import source_archive


def check(root, version, core_manifest, vector_metadata):
    if version != "16.15":
        raise ValueError("Windows Git source validation is only configured for PostgreSQL 16.15")
    core = json.loads(Path(core_manifest).read_text(encoding="utf-8-sig"))
    vector = json.loads(Path(vector_metadata).read_text(encoding="utf-8-sig"))
    if core.get("source_checkout") != source_checkout(version, root):
        raise ValueError("PostgreSQL packaged Git source identity differs from the selected upstream release tag")
    if "source_archive" in core or "source_sha256" in core:
        raise ValueError("PostgreSQL Git checkout must not claim release-tarball identity")
    if vector.get("source_archive") != source_archive("pgvector", "0.8.7", "tar.gz", root):
        raise ValueError("pgvector packaged source identity differs from selected archive")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--core-manifest", type=Path, required=True)
    parser.add_argument("--vector-metadata", type=Path, required=True)
    args = parser.parse_args()
    check(args.root, args.postgresql_version, args.core_manifest, args.vector_metadata)


if __name__ == "__main__":
    main()
