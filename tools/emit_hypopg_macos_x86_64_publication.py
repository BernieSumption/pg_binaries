#!/usr/bin/env python3
"""Emit checksum-bound HypoPG macOS PostgreSQL 18.6 Intel publication evidence."""

import json
from pathlib import Path

import emit_hypopg_macos_publication as implementation


PG_VERSION = "18.6"
ARCHITECTURE = "x86_64"
PLATFORM = f"macos-{ARCHITECTURE}"
PROFILE_ID = f"hypopg-publication-macos-{ARCHITECTURE}-{PG_VERSION}"
PIN = json.loads((Path(__file__).parent / "hypopg_macos_pins" / f"{PG_VERSION}-{ARCHITECTURE}.json").read_text())
CORE_SHA256 = PIN["core_sha256"]


def _invoke(function, *args, **kwargs):
    original = (implementation.PROFILE_ID, implementation.ARCHITECTURE, implementation.PLATFORM,
                implementation.CORE_SHA256)
    implementation.PROFILE_ID, implementation.ARCHITECTURE, implementation.PLATFORM, implementation.CORE_SHA256 = (
        PROFILE_ID, ARCHITECTURE, f"macos-{ARCHITECTURE}", CORE_SHA256)
    try:
        return function(*args, **kwargs)
    finally:
        (implementation.PROFILE_ID, implementation.ARCHITECTURE, implementation.PLATFORM,
         implementation.CORE_SHA256) = original


def emit(*args, **kwargs):
    return _invoke(implementation.emit, *args, **kwargs)


def main():
    return _invoke(implementation.main)


def __getattr__(name):
    return getattr(implementation, name)


if __name__ == "__main__":
    raise SystemExit(main())
