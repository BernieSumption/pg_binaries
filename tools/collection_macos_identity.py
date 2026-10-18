"""Pinned PostgreSQL archive identities for collection macOS publication."""

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def selected_identity(pg_version=None, architecture=None, require_complete=True):
    pg_version = pg_version or os.environ.get("COLLECTION_POSTGRESQL_VERSION", "18.6")
    architecture = architecture or os.environ.get("COLLECTION_MACOS_ARCHITECTURE", "arm64")
    if architecture not in {"arm64", "x86_64"}:
        raise ValueError("COLLECTION_MACOS_ARCHITECTURE must be arm64 or x86_64")
    pins_path = ROOT / "tools/collection_macos_pins" / f"{pg_version}-{architecture}.json"
    identity = json.loads(pins_path.read_text(encoding="utf-8"))
    if require_complete and any(identity.get(key) is None for key in ("sha256", "build_id", "source_revision")):
        raise ValueError(
            f"PostgreSQL {pg_version} macOS {architecture} identity is incomplete; "
            "fill sha256, build_id, and source_revision in tools/collection_macos_pins/<version>-<architecture>.json "
            "after the core pilot run completes"
        )
    return pg_version, architecture, identity
