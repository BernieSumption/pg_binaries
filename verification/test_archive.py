from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from verification.archive import ArchiveError, validate_archives


LICENCE = b"See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md\n"


def make_archive(path: Path, members: list[tuple[str, bytes | None, int, str | None]]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, data, mode, link in members:
            info = tarfile.TarInfo(name)
            info.mode = mode
            if link is not None:
                info.type = tarfile.SYMTYPE
                info.linkname = link
                archive.addfile(info)
            elif data is None:
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            else:
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))


class ArchiveValidationTests(unittest.TestCase):
    def test_compatible_merge_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = [("postgresql/", None, 0o755, None),
                    ("postgresql/LICENCE", LICENCE, 0o644, None),
                    ("postgresql/share/", None, 0o755, None)]
            first, second, conflict = root / "one.tar.gz", root / "two.tar.gz", root / "bad.tar.gz"
            make_archive(first, base + [("postgresql/share/data", b"same", 0o644, None)])
            make_archive(second, base + [("postgresql/share/data", b"same", 0o644, None),
                                         ("postgresql/lib/ext.so", b"module", 0o755, None)])
            make_archive(conflict, base + [("postgresql/share/data", b"different", 0o644, None)])
            self.assertIn("postgresql/lib/ext.so", validate_archives([first, second]))
            with self.assertRaisesRegex(ArchiveError, "overlapping path"):
                validate_archives([first, conflict])

    def test_rejects_escape_and_unsafe_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad_path, bad_link = root / "path.tar.gz", root / "link.tar.gz"
            make_archive(bad_path, [("postgresql/", None, 0o755, None),
                                    ("postgresql/../outside", b"x", 0o644, None),
                                    ("postgresql/LICENCE", LICENCE, 0o644, None)])
            make_archive(bad_link, [("postgresql/", None, 0o755, None),
                                    ("postgresql/LICENCE", LICENCE, 0o644, None),
                                    ("postgresql/lib", None, 0o777, "../../outside")])
            with self.assertRaisesRegex(ArchiveError, "unsafe archive path"):
                validate_archives([bad_path])
            with self.assertRaisesRegex(ArchiveError, "link escapes"):
                validate_archives([bad_link])

    def test_rejects_files_below_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "redirect.tar.gz"
            make_archive(archive, [("postgresql/", None, 0o755, None),
                                   ("postgresql/LICENCE", LICENCE, 0o644, None),
                                   ("postgresql/lib", None, 0o777, "share"),
                                   ("postgresql/lib/module.so", b"module", 0o755, None)])
            with self.assertRaisesRegex(ArchiveError, "non-directory parent"):
                validate_archives([archive])

    def test_rejects_hard_link_before_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "hardlink.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                for name in ("postgresql", "postgresql/lib"):
                    info = tarfile.TarInfo(name)
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                info = tarfile.TarInfo("postgresql/LICENCE")
                info.size = len(LICENCE)
                archive.addfile(info, io.BytesIO(LICENCE))
                info = tarfile.TarInfo("postgresql/lib/alias.so")
                info.type = tarfile.LNKTYPE
                info.linkname = "postgresql/lib/module.so"
                archive.addfile(info)
                info = tarfile.TarInfo("postgresql/lib/module.so")
                info.size = 6
                archive.addfile(info, io.BytesIO(b"module"))
            with self.assertRaisesRegex(ArchiveError, "lacks an earlier file target"):
                validate_archives([archive_path])


if __name__ == "__main__":
    unittest.main()
