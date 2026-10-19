#!/usr/bin/env python3
"""Import checksum-bound HypoPG macOS PostgreSQL 18.6 Intel evidence."""

import emit_hypopg_macos_x86_64_publication as implementation
import import_hypopg_macos_publication as importer


def _invoke(function, *args):
    original = (implementation.implementation.PROFILE_ID, implementation.implementation.ARCHITECTURE,
                implementation.implementation.PLATFORM)
    implementation.implementation.PROFILE_ID = implementation.PROFILE_ID
    implementation.implementation.ARCHITECTURE = implementation.ARCHITECTURE
    implementation.implementation.PLATFORM = f"macos-{implementation.ARCHITECTURE}"
    try:
        return function(*args)
    finally:
        (implementation.implementation.PROFILE_ID, implementation.implementation.ARCHITECTURE,
         implementation.implementation.PLATFORM) = original


def import_run(*args):
    return _invoke(importer.import_run, *args)


def main():
    return _invoke(importer.main)


def __getattr__(name):
    return getattr(importer, name)


if __name__ == "__main__":
    raise SystemExit(main())
