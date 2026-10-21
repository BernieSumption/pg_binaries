"""Check version-specific vcpkg notices in a Windows PostgreSQL archive."""

import argparse
import json
from pathlib import Path
import tarfile


NOTICES = {
    "lz4.dll": ("lz4", "1.10.0", "lz4-1.10.0-xxhash.txt",
                "support/licences/lz4-1.10.0-xxhash-notice.txt"),
    "zstd.dll": ("zstd", "1.5.7", "zstd-1.5.7-divsufsort.txt",
                 "support/licences/zstd-1.5.7-divsufsort-notice.txt"),
    "libxml2.dll": ("libxml2", "2.15.3", "libxml2-v2.15.3-dict-c.txt",
                    "support/licences/libxml2-v2.15.3-dict-c-notice.txt"),
}
LIBXML_LIST = ("libxml2-v2.15.3-list-c.txt",
               "support/licences/libxml2-v2.15.3-list-c-notice.txt")


def notice_text(data: bytes) -> bytes:
    normalized = data.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        raise ValueError("notice contains a bare carriage return")
    return normalized


def check_archive(archive_path: Path, repo: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers() if member.isfile()}

        def read(path: str) -> bytes:
            member = members.get(f"postgresql/{path}")
            if member is None:
                raise ValueError(f"archive is missing {path}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"cannot read {path}")
            return stream.read()

        ownership = json.loads(read("LICENSES/vcpkg-dll-map.json"))
        owners = {entry["dll"].lower(): entry for entry in ownership["components"]}
        for dll, (port, version, packaged_name, source_name) in NOTICES.items():
            owner = owners.get(dll.lower())
            if owner is None or owner["port"] != port or owner["version"] != version:
                raise ValueError(f"{dll} is not mapped to {port} {version}")
            expected = (repo / source_name).read_bytes()
            packaged = read(f"LICENSES/dependencies/{packaged_name}")
            if notice_text(packaged) != notice_text(expected):
                raise ValueError(f"archive notice differs from reviewed {port} {version} notice")
            bundle = read("LICENSES/dependencies/NOTICE-BUNDLE.txt")
            if packaged not in bundle:
                raise ValueError(f"NOTICE-BUNDLE.txt omits {packaged_name}")

        filename, source_name = LIBXML_LIST
        expected = (repo / source_name).read_bytes()
        packaged = read(f"LICENSES/dependencies/{filename}")
        if notice_text(packaged) != notice_text(expected):
            raise ValueError("archive notice differs from reviewed libxml2 2.15.3 list.c notice")
        if packaged not in read("LICENSES/dependencies/NOTICE-BUNDLE.txt"):
            raise ValueError(f"NOTICE-BUNDLE.txt omits {filename}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    check_archive(args.archive, args.repo)


if __name__ == "__main__":
    main()
