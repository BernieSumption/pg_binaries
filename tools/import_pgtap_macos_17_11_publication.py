#!/usr/bin/env python3
"""Import checksum-bound pgTAP macOS PostgreSQL 17.11 publication evidence."""

import json
from pathlib import Path

import emit_pgtap_macos_publication as implementation
import import_pgtap_macos_publication as importer


PG_VERSION = "17.11"
ARCHITECTURE = "arm64"
PROFILE_ID = f"pgtap-publication-macos-{ARCHITECTURE}-{PG_VERSION}"
PIN = json.loads((Path(__file__).parent / "pgtap_macos_pins" / f"{PG_VERSION}-{ARCHITECTURE}.json").read_text())
CORE_SHA256 = PIN["sha256"]


def _invoke(function, *args):
    original = (implementation.PG_VERSION, implementation.PROFILE_ID, implementation.CORE_SHA256)
    implementation.PG_VERSION, implementation.PROFILE_ID, implementation.CORE_SHA256 = (
        PG_VERSION, PROFILE_ID, CORE_SHA256)
    try:
        return function(*args)
    finally:
        implementation.PG_VERSION, implementation.PROFILE_ID, implementation.CORE_SHA256 = original


def import_run(*args):
    return _invoke(importer.import_run, *args)


def main():
    return _invoke(importer.main)


def __getattr__(name):
    return getattr(importer, name)


if __name__ == "__main__":
    raise SystemExit(main())
