import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "license_pointer", Path(__file__).resolve().parents[1] / "tools" / "license_pointer.py")
pointer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pointer)


class LicensePointerTests(unittest.TestCase):
    def test_writes_component_pointer_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pointer.write_pointer(temp, "postgresql")
            self.assertEqual(path.relative_to(temp).as_posix(), "LICENSES/postgresql/LICENCE")
            self.assertEqual(path.read_text(encoding="utf-8"), pointer.LICENSE_POINTER)
            with self.assertRaises(pointer.LicensePointerError):
                pointer.write_pointer(temp, "postgresql")

    def test_rejects_component_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ("../outside", "a/b", "a\\b", ""):
                with self.subTest(name=name), self.assertRaises(pointer.LicensePointerError):
                    pointer.write_pointer(temp, name)

    def test_verifies_exact_pointer_and_safe_members(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "payload.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                content = pointer.LICENSE_POINTER.encode("utf-8")
                member = tarfile.TarInfo("extension/LICENSES/extension/LICENCE")
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
            self.assertTrue(pointer.verify_archive(archive_path, "extension"))

    def test_rejects_missing_or_wrong_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "payload.tar.gz"
            for member_name, content in (
                ("extension/LICENSES/extension/LICENCE", b"wrong\n"),
                ("extension/other.txt", b"payload"),
            ):
                with self.subTest(member=member_name):
                    with tarfile.open(archive_path, "w:gz") as archive:
                        member = tarfile.TarInfo(member_name)
                        member.size = len(content)
                        archive.addfile(member, io.BytesIO(content))
                    with self.assertRaises(pointer.LicensePointerError):
                        pointer.verify_archive(archive_path, "extension")


if __name__ == "__main__":
    unittest.main()
