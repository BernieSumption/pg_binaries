#!/usr/bin/env python3
"""Validate an extension redistribution inventory and native Mach-O mapping."""

import argparse
import json
from pathlib import PurePosixPath
import sys
import tarfile

from publication_preflight import PreflightError, _archive_redistribution


MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}


def check_archive(path):
    _archive_redistribution(path, metadata_sibling=True)
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = {member.name.rstrip("/"): member for member in archive.getmembers()}
            inventories = [name for name in members
                           if len(name.split("/")) == 3
                           and name.split("/")[1] == "LICENSES"
                           and name.split("/")[2] == name.split("/")[0] + "-inventory.json"]
            if len(inventories) != 1:
                raise PreflightError("extension archive requires one project-named licence inventory")
            inventory_path = inventories[0]
            root = inventory_path.split("/")[0]
            inventory = json.load(archive.extractfile(members[inventory_path]))
            mapped = set()
            for component in inventory["components"]:
                for value in component["payload_paths"]:
                    mapped.add(PurePosixPath(value).as_posix().rstrip("/"))

            native = set()
            for name, member in members.items():
                if not name.startswith(root + "/"):
                    continue
                relative = name[len(root) + 1:]
                if PurePosixPath(relative).name.lower().endswith((".dylib", ".so")):
                    native.add(relative)
                elif member.isfile() and archive.extractfile(member).read(4) in MACHO_MAGICS:
                    native.add(relative)
            missing = sorted(path for path in native
                             if not any(path == payload or path.startswith(payload + "/")
                                        for payload in mapped))
            if missing:
                raise PreflightError(f"unmapped native payload: {', '.join(missing)}")
            return len(inventory["components"]), len(native)
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError,
            KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, PreflightError):
            raise
        raise PreflightError(f"cannot inspect extension licence inventory: {exc}") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="final extension .tar.gz archive")
    args = parser.parse_args()
    try:
        components, native = check_archive(args.archive)
    except (OSError, PreflightError) as exc:
        parser.error(str(exc))
    print(f"Checked {native} native payloads and redistribution evidence across {components} components")
    return 0


if __name__ == "__main__":
    sys.exit(main())
