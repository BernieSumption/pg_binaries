import tempfile
import unittest
from pathlib import Path

from platforms.macos.bundle import prefix_library


class PrefixLibraryTests(unittest.TestCase):
    def test_resolves_bare_library_name_under_dependency_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            library = prefix / "lib" / "libicuuc.78.dylib"
            library.parent.mkdir()
            library.write_bytes(b"library")

            self.assertEqual(prefix_library("libicuuc.78.dylib", prefix), library.resolve())

    def test_rejects_paths_and_files_outside_dependency_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "prefix"
            prefix.mkdir()
            self.assertIsNone(prefix_library("../libicuuc.78.dylib", prefix))
            self.assertIsNone(prefix_library("libicuuc.78.dylib", prefix))
            outside = Path(directory) / "outside.dylib"
            outside.write_bytes(b"outside")
            (prefix / "lib").mkdir()
            (prefix / "lib" / "libicuuc.78.dylib").symlink_to(outside)
            self.assertIsNone(prefix_library("libicuuc.78.dylib", prefix))


if __name__ == "__main__":
    unittest.main()
