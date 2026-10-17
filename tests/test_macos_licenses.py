import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/macos/licenses.py"
LIBXML2_NOTICES = pathlib.Path(__file__).resolve().parent / "fixtures/libxml2-2.15.4"
POSTGRESQL_COPYRIGHT = pathlib.Path(__file__).resolve().parent / "fixtures/postgresql-COPYRIGHT"


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
        (self.root / "lib").mkdir()
        (self.root / "lib" / self.library.name).write_text("bundled library")
        (self.root / "lib/libpq.dylib").write_text("primary payload")
        (self.root / "LICENSES").mkdir()
        (self.root / "LICENSES/PostgreSQL.txt").write_text("PostgreSQL licence")
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
        args.extend(["--component", "postgresql", "--version", "18.1", "--source-url", "https://example.invalid/postgresql.tar.gz",
                     "--source-sha256", "b" * 64])
        return subprocess.run(args, capture_output=True, text=True)

    def test_collects_source_archive_license_with_pinned_identity(self):
        result = self.run_licenses()
        self.assertEqual(result.returncode, 0, result.stderr)
        inventory = json.loads((self.root / "LICENSES/inventory.json").read_text())
        self.assertEqual(inventory["schema_version"], 1)
        primary, dependency = inventory["components"]
        self.assertEqual(primary["component"], "postgresql")
        self.assertEqual(primary["payload_paths"], ["lib/libpq.dylib"])
        self.assertEqual(primary["source_sha256"], "b" * 64)
        self.assertEqual(dependency["component"], "lz4")
        self.assertEqual(dependency["version"], "1.10.0")
        self.assertEqual(dependency["payload_paths"], ["lib/" + self.library.name])
        for key in ("source_url", "source_sha256", "license_source"):
            self.assertEqual(dependency[key], self.manifest["components"][0][key])
        for component in inventory["components"]:
            self.assertEqual(component["redistribution_review"]["status"], "pending")
            self.assertEqual(component["redistribution_review"]["source_obligation"], "unknown")
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
        self.assertEqual([(item["package"], item["version"]) for item in inventory["components"][1:]], [("lz4", "1.10.0")])

    def test_rejects_missing_bundled_payload(self):
        (self.root / "lib" / self.library.name).unlink()
        result = self.run_licenses()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing or unsafe bundled library payload", result.stderr)

    def test_preserves_additional_notices(self):
        notice = self.license_path.parent / "NOTICE"
        notice.write_text("Additional attribution")
        self.manifest["components"][0]["additional_license_files"] = ["licenses/NOTICE"]
        self.write_manifest()
        result = self.run_licenses()
        self.assertEqual(result.returncode, 0, result.stderr)
        dependency = json.loads((self.root / "LICENSES/inventory.json").read_text())["components"][1]
        self.assertEqual((self.root / "LICENSES" / dependency["additional_license_files"][0]).read_text(), "Additional attribution")

    def test_libxml2_review_requires_all_exact_notices(self):
        library = self.prefix / "lib/libxml2.16.dylib"
        library.write_text("source-built libxml2 fixture")
        (self.root / "lib/libxml2.16.dylib").write_text("bundled libxml2 fixture")
        bundled = json.loads((self.root / "bundled-dependencies.json").read_text())
        bundled[library.name] = str(library)
        (self.root / "bundled-dependencies.json").write_text(json.dumps(bundled))
        notices = self.manifest_path.parent / "licenses"
        for source, target in (("Copyright", "libxml2-Copyright.txt"),
                               ("dict-notice.txt", "libxml2-2.15.4-dict.txt"),
                               ("list-notice.txt", "libxml2-2.15.4-list.txt")):
            (notices / target).write_bytes((LIBXML2_NOTICES / source).read_bytes())
        self.manifest["components"].append({
            "package": "libxml2", "version": "2.15.4", "libraries": [library.name],
            "license_file": "licenses/libxml2-Copyright.txt",
            "license_source": "libxml2-2.15.4/Copyright",
            "source_url": "https://download.gnome.org/sources/libxml2/2.15/libxml2-2.15.4.tar.xz",
            "source_sha256": "98087fd181d9070724f3fbc65c7377db03038eb92bd882374daff44940138821",
            "additional_license_files": ["licenses/libxml2-2.15.4-dict.txt", "licenses/libxml2-2.15.4-list.txt"],
        })
        self.write_manifest()
        result = self.run_licenses()
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = json.loads((self.root / "LICENSES/inventory.json").read_text())["components"]
        xml = next(entry for entry in entries if entry["component"] == "libxml2")
        self.assertEqual(xml["redistribution_review"]["status"], "resolved")
        (notices / "libxml2-2.15.4-list.txt").write_text("changed notice")
        result = self.run_licenses()
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = json.loads((self.root / "LICENSES/inventory.json").read_text())["components"]
        xml = next(entry for entry in entries if entry["component"] == "libxml2")
        self.assertEqual(xml["redistribution_review"]["status"], "pending")

    def test_pgvector_without_dependencies_has_primary_inventory(self):
        (self.root / "bundled-dependencies.json").write_text("{}")
        (self.root / "LICENSES/pgvector.txt").write_text("pgvector licence")
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.root),
                                 "--component", "pgvector", "--version", "0.8.7", "--source-url",
                                 "https://example.invalid/pgvector.tar.gz"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        inventory = json.loads((self.root / "LICENSES/inventory.json").read_text())
        self.assertEqual(len(inventory["components"]), 1)
        self.assertEqual(inventory["components"][0]["component"], "pgvector")

    def test_rejects_homebrew_dependency_in_source_bundle(self):
        bundled = json.loads((self.root / "bundled-dependencies.json").read_text())
        bundled["liblz4-homebrew.dylib"] = "/opt/homebrew/Cellar/lz4/1.10.0/lib/liblz4-homebrew.dylib"
        (self.root / "bundled-dependencies.json").write_text(json.dumps(bundled))
        result = self.run_licenses()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("still includes Homebrew library", result.stderr)

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

    def test_rejects_malformed_primary_source_digest(self):
        result = self.run_licenses()
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.root), str(self.manifest_path),
                                 "--component", "postgresql", "--version", "18.6",
                                 "--source-url", "https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2",
                                 "--source-sha256", "not-a-digest"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("primary source_sha256", result.stderr)

    def test_selected_postgresql_reviews_require_exact_source_and_licence(self):
        (self.root / "bundled-dependencies.json").write_text("{}")
        (self.root / "LICENSES/PostgreSQL.txt").write_bytes(POSTGRESQL_COPYRIGHT.read_bytes())
        digests = {
            "15.19": "e1a64a87a46b825b88c082e4518161a47aab53c45694964f8ba1df28f7859f89",
            "16.15": "c1575341fa7bd40f5274ea465b34390f4dc64cdd0770af327005caaeb9f6b7ed",
            "17.11": "dd27f2b3c59e73ed14aa3324901242bf69a032a6347805f274e6260322d42979",
            "18.6": "555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f",
        }
        for version, digest in digests.items():
            with self.subTest(version=version):
                command = [sys.executable, str(SCRIPT), str(self.root), "--component", "postgresql",
                           "--version", version, "--source-url",
                           f"https://ftp.postgresql.org/pub/source/v{version}/postgresql-{version}.tar.bz2",
                           "--source-sha256", digest]
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                entry = json.loads((self.root / "LICENSES/inventory.json").read_text())["components"][0]
                self.assertEqual(entry["redistribution_review"]["status"], "resolved")
                command[-1] = "0" * 64
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                entry = json.loads((self.root / "LICENSES/inventory.json").read_text())["components"][0]
                self.assertEqual(entry["redistribution_review"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
