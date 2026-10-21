import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.license_repack.repack import RepackError, repack, verify_repack
from tools.license_pointer import LICENSE_POINTER


class RepackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.tar.gz"

    def tearDown(self):
        self.temp.cleanup()

    def make_archive(self, members):
        with tarfile.open(self.source, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            for name, kind, data, mode, linkname in members:
                info = tarfile.TarInfo(name)
                info.mode = mode
                info.mtime = 1700000000
                if kind == "dir":
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                elif kind == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = linkname
                    archive.addfile(info)
                elif kind == "hardlink":
                    info.type = tarfile.LNKTYPE
                    info.linkname = linkname
                    archive.addfile(info)
                else:
                    info.size = len(data)
                    import io
                    archive.addfile(info, io.BytesIO(data))

    def test_repack_removes_selected_text_and_preserves_all_other_members(self):
        self.make_archive([
            ("pgaudit", "dir", b"", 0o755, ""),
            ("pgaudit/LICENSES", "dir", b"", 0o755, ""),
            ("pgaudit/LICENSES/pgAudit.txt", "file", b"old licence", 0o644, ""),
            ("pgaudit/LICENSES/pgaudit-inventory.json", "file", b"{}\n", 0o640, ""),
            ("pgaudit/lib", "dir", b"", 0o755, ""),
            ("pgaudit/lib/module.so", "file", b"binary bytes", 0o755, ""),
            ("pgaudit/lib/module-link.so", "hardlink", b"", 0o755, "pgaudit/lib/module.so"),
            ("pgaudit/lib/module-alias.so", "symlink", b"", 0o777, "module.so"),
            ("metadata.json", "file", b"metadata", 0o644, ""),
        ])
        output, report = self.root / "out.tar.gz", self.root / "report.json"
        result = repack(self.source, "pgaudit", output, report,
                        ["pgaudit/LICENSES/pgAudit.txt"])
        verify_repack(self.source, output, "pgaudit", {"pgaudit/LICENSES/pgAudit.txt"})
        with tarfile.open(output) as archive:
            entries = {m.name.rstrip("/"): m for m in archive.getmembers()}
            self.assertNotIn("pgaudit/LICENSES/pgAudit.txt", entries)
            self.assertEqual(entries["pgaudit/LICENSES/pgaudit-inventory.json"].mode, 0o640)
            self.assertEqual(entries["pgaudit/lib/module.so"].mode, 0o755)
            self.assertEqual(entries["pgaudit/lib/module-link.so"].linkname,
                             "pgaudit/lib/module.so")
            self.assertEqual(entries["pgaudit/lib/module-alias.so"].linkname, "module.so")
            pointer = archive.extractfile(entries["pgaudit/LICENSES/pgaudit/LICENCE"])
            self.assertEqual(pointer.read(), LICENSE_POINTER.encode())
        saved = json.loads(report.read_text())
        self.assertEqual(saved["output_sha256"], result["output_sha256"])
        self.assertTrue(saved["runtime_members_unchanged"])

    def test_rejects_unsafe_and_duplicate_names(self):
        for path in ("../outside", "/absolute", "component//empty"):
            with self.subTest(path=path):
                self.make_archive([(path, "file", b"x", 0o644, "")])
                with self.assertRaises(RepackError):
                    repack(self.source, "component", self.root / "out.tar.gz",
                           self.root / "report.json", [])
        self.make_archive([
            ("component/file", "file", b"one", 0o644, ""),
            ("component/file", "file", b"two", 0o644, ""),
        ])
        with self.assertRaisesRegex(RepackError, "duplicate"):
            repack(self.source, "component", self.root / "out.tar.gz",
                   self.root / "report.json", [])

    def test_rejects_escaping_links_and_pointer_overwrite(self):
        self.make_archive([
            ("component", "dir", b"", 0o755, ""),
            ("component/escape", "symlink", b"", 0o777, "../../outside"),
        ])
        with self.assertRaisesRegex(RepackError, "escapes"):
            repack(self.source, "component", self.root / "out.tar.gz",
                   self.root / "report.json", [])

        self.make_archive([
            ("component", "dir", b"", 0o755, ""),
            ("component/LICENSES/component/LICENCE", "file", b"old", 0o644, ""),
        ])
        with self.assertRaisesRegex(RepackError, "overwrite"):
            repack(self.source, "component", self.root / "out.tar.gz",
                   self.root / "report.json", [])

    def test_rejects_removing_a_hardlink_target(self):
        self.make_archive([
            ("component", "dir", b"", 0o755, ""),
            ("component/LICENSES", "dir", b"", 0o755, ""),
            ("component/LICENSES/old.txt", "file", b"licence", 0o644, ""),
            ("component/retained-link", "hardlink", b"", 0o644,
             "component/LICENSES/old.txt"),
        ])
        with self.assertRaisesRegex(RepackError, "hardlink target"):
            repack(self.source, "component", self.root / "out.tar.gz",
                   self.root / "report.json", ["component/LICENSES/old.txt"])


if __name__ == "__main__":
    unittest.main()
