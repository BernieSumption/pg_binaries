#!/usr/bin/env python3
"""Check an extension archive's licence pointer."""

import argparse
import json
import sys
import tarfile

from publication_preflight import PreflightError, _archive_license_pointer, _coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="final extension archive")
    args = parser.parse_args()
    try:
        with tarfile.open(args.archive, "r:gz") as archive:
            member = archive.getmember("metadata.json")
            if not member.isfile() or member.size > 1024 * 1024:
                raise PreflightError("extension archive requires a regular metadata.json file")
            metadata = json.load(archive.extractfile(member))
            if not isinstance(metadata, dict) or not isinstance(metadata.get("project"), str):
                raise PreflightError("extension metadata requires a project")
        component = _coverage.archive_project_name(metadata["project"])
        _archive_license_pointer(args.archive, component, metadata_sibling=True)
    except (OSError, KeyError, TypeError, ValueError, tarfile.TarError) as exc:
        if not isinstance(exc, PreflightError):
            exc = PreflightError(f"cannot inspect extension archive: {exc}")
        parser.error(str(exc))
    print(f"PASS: licence pointer in {args.archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
