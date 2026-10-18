import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "stage_windows_postgres_import_library",
    ROOT / "tools" / "stage_windows_postgres_import_library.py")
stager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stager)


class StageWindowsPostgresImportLibraryTests(unittest.TestCase):
    def test_stages_byte_identical_import_library_without_removing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source = directory / "postgres.exe.lib"
            target = directory / "postgres.lib"
            source.write_bytes(b"generated import library\x00\xff")
            staged = stager.stage_import_library(directory)
            self.assertEqual(staged, target)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(stager.sha256(target), stager.sha256(source))
            self.assertTrue(source.is_file())
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps({"windows_import_library": {
                "filename": "postgres.lib", "alias_of": "postgres.exe.lib",
                "sha256": stager.sha256(target),
            }}), encoding="utf-8")
            self.assertEqual(stager.verify_import_library(directory, manifest), target)
            target.write_bytes(b"different content")
            with self.assertRaisesRegex(ValueError, "differs"):
                stager.verify_import_library(directory, manifest)

    def test_fails_if_source_is_missing_or_target_already_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with self.assertRaisesRegex(ValueError, "missing"):
                stager.stage_import_library(directory)
            source = directory / "postgres.exe.lib"
            target = directory / "postgres.lib"
            source.write_bytes(b"source")
            target.write_bytes(b"existing")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                stager.stage_import_library(directory)
            self.assertEqual(target.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
