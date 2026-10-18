import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools/inventory_cargo_licenses.py"
spec = importlib.util.spec_from_file_location("inventory_cargo_licenses", MODULE_PATH)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CargoLicenseInventoryTests(unittest.TestCase):
    def test_records_sorted_packages_and_hashed_license_and_notice_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "LICENSE").write_text("root license\n")
            crate = root / "vendor/example-1.0"
            crate.mkdir(parents=True)
            (crate / "Cargo.toml").write_text("[package]\nname='example'\n")
            (crate / "LICENSE-MIT").write_text("MIT terms\n")
            (crate / "NOTICE").write_text("notice text\n")
            metadata = {"packages": [{
                "name": "example", "version": "1.0.0", "source": "registry+https://example.invalid",
                "license": "MIT", "license_file": None, "manifest_path": str(crate / "Cargo.toml"),
            }]}

            result = checker.inventory(root, metadata)

            self.assertEqual(result["source_files"][0]["path"], "LICENSE")
            self.assertEqual([f["path"] for f in result["packages"][0]["license_notice_files"]], ["LICENSE-MIT", "NOTICE"])
            self.assertEqual(len(result["packages"][0]["license_notice_files"][0]["sha256"]), 64)

    def test_rejects_package_without_license_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crate = root / "crate"
            crate.mkdir()
            manifest = crate / "Cargo.toml"
            manifest.touch()
            metadata = {"packages": [{"name": "missing", "version": "1", "manifest_path": str(manifest)}]}

            with self.assertRaisesRegex(ValueError, "no Cargo licence metadata"):
                checker.inventory(root, metadata)

    def test_rejects_missing_declared_license_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crate = root / "crate"
            crate.mkdir()
            manifest = crate / "Cargo.toml"
            manifest.touch()
            metadata = {"packages": [{
                "name": "missing-file", "version": "1", "license_file": "LICENSE.txt",
                "manifest_path": str(manifest),
            }]}

            with self.assertRaisesRegex(ValueError, "invalid or missing license_file"):
                checker.inventory(root, metadata)


if __name__ == "__main__":
    unittest.main()
