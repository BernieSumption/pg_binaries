#!/usr/bin/env python3
"""Emit checksum-bound HypoPG macOS PostgreSQL 18.6 Intel publication evidence."""

import emit_hypopg_macos_publication as implementation


PG_VERSION = "18.6"
ARCHITECTURE = "x86_64"
PLATFORM = f"macos-{ARCHITECTURE}"
PROFILE_ID = f"hypopg-publication-macos-{ARCHITECTURE}-{PG_VERSION}"


def _invoke(function, *args, **kwargs):
    original = (implementation.PROFILE_ID, implementation.ARCHITECTURE, implementation.PLATFORM)
    implementation.PROFILE_ID, implementation.ARCHITECTURE, implementation.PLATFORM = (
        PROFILE_ID, ARCHITECTURE, f"macos-{ARCHITECTURE}")
    try:
        return function(*args, **kwargs)
    finally:
        (implementation.PROFILE_ID, implementation.ARCHITECTURE, implementation.PLATFORM) = original


def emit(*args, **kwargs):
    return _invoke(implementation.emit, *args, **kwargs)


def main():
    return _invoke(implementation.main)


def __getattr__(name):
    return getattr(implementation, name)


if __name__ == "__main__":
    raise SystemExit(main())
