"""Write an ephemeral inventory selection for one checked Linux assembly."""

import argparse
import hashlib
import json
from pathlib import Path
import re


class AssemblyInventoryError(ValueError):
    pass


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_assembly_inventory(*, core_archive, extension_archive, postgresql_version,
                             extension_version, platform, output):
    """Bind two existing candidate archives to one exact, assembly-only target."""
    if not re.fullmatch(r"\d+\.\d+", postgresql_version):
        raise AssemblyInventoryError("PostgreSQL version must be major.minor")
    if not re.fullmatch(r"\d+(?:\.\d+)+", extension_version):
        raise AssemblyInventoryError("extension version is invalid")
    if platform not in {"linux-x86_64", "linux-arm64"}:
        raise AssemblyInventoryError("platform must be linux-x86_64 or linux-arm64")
    core_archive, extension_archive = Path(core_archive), Path(extension_archive)
    core_name = f"postgresql-{postgresql_version}-{platform}.tar.gz"
    extension_name = f"pgvector-{extension_version}-postgresql-{postgresql_version}-{platform}.tar.gz"
    if core_archive.name != core_name or extension_archive.name != extension_name:
        raise AssemblyInventoryError("archive filenames do not match the selected target")
    if not core_archive.is_file() or not extension_archive.is_file():
        raise AssemblyInventoryError("selected archive is missing")
    inventory = {
        "schema_version": 1,
        "candidate_status": "assembly-only",
        "postgresql": {postgresql_version: {"downloads": {platform: {
            "url": f"https://assembly.invalid/{core_name}", "sha256": _sha256(core_archive)}}}},
        "extensions": {"vector": {extension_version: {"downloads": {platform: [{
            "url": f"https://assembly.invalid/{extension_name}",
            "sha256": _sha256(extension_archive),
            "postgresql_support": {"from": postgresql_version, "to": postgresql_version},
        }]}}}},
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    return inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("core-archive", "extension-archive", "postgresql-version",
                   "extension-version", "platform", "output"):
        parser.add_argument("--" + option, required=True)
    args = vars(parser.parse_args(argv))
    args["core_archive"] = args.pop("core_archive")
    args["extension_archive"] = args.pop("extension_archive")
    try:
        write_assembly_inventory(**args)
    except (AssemblyInventoryError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
