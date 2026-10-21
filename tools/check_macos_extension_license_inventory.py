#!/usr/bin/env python3
"""Validate an extension licence pointer and report native Mach-O payloads."""

import argparse
import json
from pathlib import PurePosixPath
import sys
import tarfile

from publication_preflight import PreflightError, _archive_license_pointer, _coverage


MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}


def check_archive(path):
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = {member.name.rstrip("/"): member for member in archive.getmembers()}
            metadata_member = members.get("metadata.json")
            if metadata_member is None or not metadata_member.isfile() or metadata_member.size > 1024 * 1024:
                raise PreflightError("extension archive requires a regular metadata.json file")
            metadata = json.load(archive.extractfile(metadata_member))
            if not isinstance(metadata, dict) or not isinstance(metadata.get("project"), str):
                raise PreflightError("extension metadata requires a project")
            component = _coverage.archive_project_name(metadata["project"])
            root = component
            _archive_license_pointer(path, component, metadata_sibling=True)

            native = set()
            for name, member in members.items():
                if not name.startswith(root + "/"):
                    continue
                relative = name[len(root) + 1:]
                if PurePosixPath(relative).name.lower().endswith((".dylib", ".so")):
                    native.add(relative)
                elif member.isfile() and archive.extractfile(member).read(4) in MACHO_MAGICS:
                    native.add(relative)
            return 1, len(native)
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError,
            KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, PreflightError):
            raise
        raise PreflightError(f"cannot inspect extension archive: {exc}") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="final extension .tar.gz archive")
    args = parser.parse_args()
    try:
        components, native = check_archive(args.archive)
    except (OSError, PreflightError) as exc:
        parser.error(str(exc))
    print(f"Checked the licence pointer and {native} native payloads across {components} component")
    return 0


if __name__ == "__main__":
    sys.exit(main())
