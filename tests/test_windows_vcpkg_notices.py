import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/windows"))
import check_vcpkg_notices


class WindowsVcpkgNoticeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.archive_path = Path(self.temp.name) / "postgresql.tar.gz"
        self.entries = {
            "LICENSES/vcpkg-dll-map.json": b'{"components":['
            b'{"dll":"zstd.dll","port":"zstd","version":"1.5.7"},'
            b'{"dll":"libxml2.dll","port":"libxml2","version":"2.15.3"}]}',
        }
        self.bundle = bytearray()
        for filename, source in (
                ("zstd-1.5.7-divsufsort.txt", "zstd-1.5.7-divsufsort-notice.txt"),
                ("libxml2-v2.15.3-dict-c.txt", "libxml2-v2.15.3-dict-c-notice.txt"),
                ("libxml2-v2.15.3-list-c.txt", "libxml2-v2.15.3-list-c-notice.txt")):
            content = (ROOT / "support/licences" / source).read_bytes()
            self.entries[f"LICENSES/dependencies/{filename}"] = content
            self.bundle.extend(content)
        self.entries["LICENSES/dependencies/NOTICE-BUNDLE.txt"] = bytes(self.bundle)
        self._write_archive()

    def tearDown(self):
        self.temp.cleanup()

    def _write_archive(self):
        with tarfile.open(self.archive_path, "w:gz") as archive:
            for path, data in self.entries.items():
                member = tarfile.TarInfo(f"postgresql/{path}")
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))

    def test_accepts_exact_mapped_notices_in_archive(self):
        check_vcpkg_notices.check_archive(self.archive_path, ROOT)

    def test_accepts_windows_checkout_line_endings(self):
        for path, content in list(self.entries.items()):
            if path.startswith("LICENSES/dependencies/"):
                self.entries[path] = content.replace(b"\n", b"\r\n")
        self._write_archive()
        check_vcpkg_notices.check_archive(self.archive_path, ROOT)

    def test_rejects_changed_notice_text_with_windows_line_endings(self):
        path = "LICENSES/dependencies/zstd-1.5.7-divsufsort.txt"
        self.entries[path] = self.entries[path].replace(b"\n", b"\r\n") + b"altered\r\n"
        self._write_archive()
        with self.assertRaisesRegex(ValueError, "archive notice differs"):
            check_vcpkg_notices.check_archive(self.archive_path, ROOT)

    def test_rejects_wrong_selected_version(self):
        self.entries["LICENSES/vcpkg-dll-map.json"] = self.entries[
            "LICENSES/vcpkg-dll-map.json"].replace(b"1.5.7", b"1.5.6")
        self._write_archive()
        with self.assertRaisesRegex(ValueError, "not mapped to zstd 1.5.7"):
            check_vcpkg_notices.check_archive(self.archive_path, ROOT)

    def test_rejects_notice_missing_from_final_archive(self):
        del self.entries["LICENSES/dependencies/libxml2-v2.15.3-list-c.txt"]
        self._write_archive()
        with self.assertRaisesRegex(ValueError, "archive is missing"):
            check_vcpkg_notices.check_archive(self.archive_path, ROOT)


if __name__ == "__main__":
    unittest.main()
