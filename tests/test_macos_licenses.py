import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/macos/licenses.py"


class MacOSLicenseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.temp.name)
        self.prefix = self.base / "prefix"
        self.manifest_path = self.prefix / "share/pg_binaries/source-dependencies.json"
        self.license_path = self.manifest_path.parent / "licenses/lz4-1.10.0.txt"
        self.license_path.parent.mkdir(parents=True)
        self.license_path.write_text("LZ4 licence text\n")
        self.library = self.prefix / "lib/liblz4.1.10.0.dylib"
        self.library.parent.mkdir(parents=True)
        self.library.touch()
        self.root = self.base / "package"
        self.root.mkdir()
        (self.root / "bundled-dependencies.json").write_text(json.dumps({
            "liblz4.1.10.0.dylib": str(self.library),
        }))
        self.manifest = {
            "schema_version": 1,
            "components": [{
                "package": "lz4", "version": "1.10.0",
                "libraries": [self.library.name],
                "license_file": "licenses/lz4-1.10.0.txt",
                "license_source": "archive:lib/LICENSE",
                "source_url": "https://example.invalid/lz4-1.10.0.tar.gz",
                "source_sha256": "a" * 64,
            }],
        }
        self.write_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self):
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(self.manifest))

    def run_licenses(self, with_manifest=True):
        args = [sys.executable, str(SCRIPT), str(self.root)]
        if with_manifest:
            args.append(str(self.manifest_path))
        return subprocess.run(args, capture_output=True, text=True)

    def test_collects_source_archive_license_with_pinned_identity(self):
        result = self.run_licenses()
        self.assertEqual(result.returncode, 0, result.stderr)
        inventory = json.loads((self.root / "LICENSES/inventory.json").read_text())
        self.assertEqual(inventory[0]["package"], "lz4")
        self.assertEqual(inventory[0]["version"], "1.10.0")
        self.assertEqual(set(inventory[0]), {
            "package", "version", "libraries", "license_file", "license_source",
        })
        self.assertEqual((self.root / "LICENSES/lz4-1.10.0.txt").read_text(), "LZ4 licence text\n")

    def test_allows_declared_but_unbundled_source_libraries_and_components(self):
        extra_license = self.manifest_path.parent / "licenses/zstd-1.5.7.txt"
        extra_license.write_text("Zstandard licence text\n")
        self.manifest["components"][0]["libraries"].append("liblz4-unbundled.dylib")
        self.manifest["components"].append({
            "package": "zstd", "version": "1.5.7",
            "libraries": ["libzstd-unbundled.dylib"],
            "license_file": "licenses/zstd-1.5.7.txt",
            "license_source": "archive:LICENSE",
            "source_url": "https://example.invalid/zstd-1.5.7.tar.gz",
            "source_sha256": "b" * 64,
        })
        self.write_manifest()
        result = self.run_licenses()
        self.assertEqual(result.returncode, 0, result.stderr)
        inventory = json.loads((self.root / "LICENSES/inventory.json").read_text())
        self.assertEqual([(item["package"], item["version"]) for item in inventory], [("lz4", "1.10.0")])

    def test_rejects_package_version_shared_by_source_and_homebrew(self):
        bundled = json.loads((self.root / "bundled-dependencies.json").read_text())
        bundled["liblz4-homebrew.dylib"] = "/opt/homebrew/Cellar/lz4/1.10.0/lib/liblz4-homebrew.dylib"
        (self.root / "bundled-dependencies.json").write_text(json.dumps(bundled))
        result = self.run_licenses()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("present from both source archives and Homebrew", result.stderr)

    def test_rejects_source_library_without_manifest(self):
        result = self.run_licenses(with_manifest=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("provide a source dependency manifest", result.stderr)

    def test_rejects_missing_license_text(self):
        self.license_path.unlink()
        result = self.run_licenses()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing or unsafe licence text", result.stderr)

    def test_rejects_missing_source_version(self):
        self.manifest["components"][0]["version"] = ""
        self.write_manifest()
        result = self.run_licenses()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("require package, version", result.stderr)


if __name__ == "__main__":
    unittest.main()
