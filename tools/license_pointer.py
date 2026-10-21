"""Write and verify the licence pointer included in each download."""

import argparse
from pathlib import Path
import tarfile


LICENSES_URL = "https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md"
LICENSE_POINTER = f"See {LICENSES_URL}\n"


class LicensePointerError(ValueError):
    pass


def write_pointer(payload_root, component):
    """Create LICENSES/<component>/LICENCE under payload_root, without overwrite."""
    if not isinstance(component, str) or not component or component in {".", ".."} or "/" in component or "\\" in component:
        raise LicensePointerError(f"invalid component name: {component!r}")
    path = Path(payload_root) / "LICENSES" / component / "LICENCE"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise LicensePointerError(f"licence pointer already exists: {path}")
    path.write_text(LICENSE_POINTER, encoding="utf-8")
    return path


def verify_archive(archive_path, component):
    """Verify the exact component licence pointer in a project-rooted archive."""
    if not isinstance(component, str) or not component or component in {".", ".."} or "/" in component or "\\" in component:
        raise LicensePointerError(f"invalid component name: {component!r}")
    expected = f"{component}/LICENSES/{component}/LICENCE"
    try:
        with tarfile.open(archive_path, "r:*") as archive:
            found = []
            for member in archive.getmembers():
                if member.name == expected:
                    if not member.isfile():
                        raise LicensePointerError(f"licence pointer is not a regular file: {expected}")
                    found.append(member)
            if len(found) != 1:
                raise LicensePointerError(f"archive is missing {expected}")
            stream = archive.extractfile(found[0])
            if stream is None or stream.read() != LICENSE_POINTER.encode("utf-8"):
                raise LicensePointerError(f"archive has an invalid {expected}")
    except (OSError, tarfile.TarError) as exc:
        raise LicensePointerError(f"cannot read archive: {archive_path}") from exc
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    writer = subcommands.add_parser("write")
    writer.add_argument("payload_root", type=Path)
    writer.add_argument("component")
    verifier = subcommands.add_parser("verify")
    verifier.add_argument("archive", type=Path)
    verifier.add_argument("component")
    args = parser.parse_args()
    try:
        if args.command == "write":
            write_pointer(args.payload_root, args.component)
        else:
            verify_archive(args.archive, args.component)
    except LicensePointerError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
