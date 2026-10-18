#!/usr/bin/env python3
"""Emit checksum-bound pgTAP macOS PostgreSQL 17.11 Intel publication evidence."""

import json
from pathlib import Path

import emit_pgtap_macos_x86_64_publication as implementation


PG_VERSION = "17.11"
ARCHITECTURE = "x86_64"
PROFILE_ID = f"pgtap-publication-macos-{ARCHITECTURE}-{PG_VERSION}"
PIN = json.loads((Path(__file__).parent / "pgtap_macos_pins" / f"{PG_VERSION}-{ARCHITECTURE}.json").read_text())
CORE_SHA256 = PIN["sha256"]


def _invoke(function, *args, **kwargs):
    original = (implementation.PG_VERSION, implementation.PROFILE_ID, implementation.CORE_SHA256)
    implementation.PG_VERSION, implementation.PROFILE_ID, implementation.CORE_SHA256 = (
        PG_VERSION, PROFILE_ID, CORE_SHA256)
    try:
        return function(*args, **kwargs)
    finally:
        implementation.PG_VERSION, implementation.PROFILE_ID, implementation.CORE_SHA256 = original


def emit(*args, **kwargs):
    return _invoke(implementation.emit, *args, **kwargs)


def main():
    return _invoke(implementation.main)


def __getattr__(name):
    return getattr(implementation, name)


if __name__ == "__main__":
    raise SystemExit(main())
