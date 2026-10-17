import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
WRITER = REPO / "tools/write_linux_license_inventory.py"
PREFLIGHT_SPEC = importlib.util.spec_from_file_location(
    "publication_preflight", REPO / "tools/publication_preflight.py")
publication_preflight = importlib.util.module_from_spec(PREFLIGHT_SPEC)
PREFLIGHT_SPEC.loader.exec_module(publication_preflight)


class LinuxLicenseInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / "postgresql"
        for directory in ("bin", "include", "lib", "libexec", "share", "lib/runtime", "LICENSES"):
            (self.archive / directory).mkdir(parents=True, exist_ok=True)
        (self.archive / "LICENSES/PostgreSQL.txt").write_text("PostgreSQL license\n")
        (self.archive / "LICENSES/libexample1.copyright").write_text("Package copyright\n")
        (self.archive / "lib/runtime/libexample.so").write_bytes(b"runtime library")
        self.mapping = self.root / "runtime.tsv"
        self.mapping.write_text("libexample1\tlib/runtime/libexample.so\n")
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        dpkg_query = fake_bin / "dpkg-query"
        dpkg_query.write_text("#!/bin/sh\nprintf '1.2.3-4ubuntu5\\n'\n")
        dpkg_query.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}

    def tearDown(self):
        self.temp.cleanup()

    def write_inventory(self, reviews=None):
        command = ["python3", str(WRITER), str(self.archive), "18.6", str(self.mapping)]
        if reviews is not None:
            path = self.root / "reviews.json"
            path.write_text(json.dumps(reviews), encoding="utf-8")
            command.extend(["--reviews", str(path)])
        return subprocess.run(
            command,
            env=self.env, capture_output=True, text=True,
        )

    def reviewed_components(self):
        return {"schema_version": 1, "components": [
            {"component": "postgresql", "version": "18.6", "redistribution_review": {
                "status": "resolved", "basis": "PostgreSQL licence reviewed",
                "source_obligation": "none"}},
            {"component": "runtime-package", "package": "libexample1",
             "version": "1.2.3-4ubuntu5", "redistribution_review": {
                "status": "resolved", "basis": "Fixture package terms reviewed",
                "source_obligation": "source-links",
                "source_links": ["https://example.test/source.tar.gz"]}},
        ]}

    def test_maps_postgresql_and_each_copied_runtime_library(self):
        result = self.write_inventory()
        self.assertEqual(result.returncode, 0, result.stderr)
        inventory = json.loads((self.archive / "LICENSES/inventory.json").read_text())
        self.assertEqual(inventory["schema_version"], 1)
        postgres, runtime = inventory["components"]
        self.assertEqual((postgres["component"], postgres["version"]), ("postgresql", "18.6"))
        self.assertEqual(postgres["payload_paths"], ["bin", "include", "lib", "libexec", "share"])
        self.assertEqual(runtime["component"], "runtime-package")
        self.assertEqual(runtime["package"], "libexample1")
        self.assertEqual(runtime["version"], "1.2.3-4ubuntu5")
        self.assertEqual(runtime["payload_paths"], ["lib/runtime/libexample.so"])
        self.assertTrue(runtime["license_source"].startswith("https://"))

    def test_attaches_only_explicit_complete_redistribution_reviews(self):
        result = self.write_inventory(self.reviewed_components())
        self.assertEqual(result.returncode, 0, result.stderr)
        components = json.loads((self.archive / "LICENSES/inventory.json").read_text())["components"]
        self.assertEqual(components[0]["redistribution_review"]["source_obligation"], "none")
        self.assertEqual(components[1]["redistribution_review"]["source_links"],
                         ["https://example.test/source.tar.gz"])

        archive = self.root / "postgresql.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            output.add(self.archive, arcname="postgresql")
        publication_preflight._archive_redistribution(archive)

    def test_rejects_incomplete_or_unresolved_redistribution_reviews(self):
        reviews = self.reviewed_components()
        reviews["components"].pop()
        result = self.write_inventory(reviews)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing=", result.stderr)
        self.assertFalse((self.archive / "LICENSES/inventory.json").exists())

        reviews = self.reviewed_components()
        reviews["components"][1]["redistribution_review"]["status"] = "pending"
        result = self.write_inventory(reviews)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unresolved redistribution review", result.stderr)
        self.assertFalse((self.archive / "LICENSES/inventory.json").exists())

    def test_fails_when_runtime_payload_is_missing(self):
        (self.archive / "lib/runtime/libexample.so").unlink()
        result = self.write_inventory()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing non-empty runtime payload", result.stderr)

    def test_fails_when_license_text_is_missing(self):
        (self.archive / "LICENSES/libexample1.copyright").unlink()
        result = self.write_inventory()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing non-empty license text", result.stderr)

    def test_glibc_records_exact_source_and_complete_license_texts(self):
        (self.archive / "lib/glibc").mkdir()
        (self.archive / "lib/glibc/libc.so.6").write_bytes(b"glibc")
        (self.archive / "LICENSES/libc6.copyright").write_text("glibc copyright\n")
        for name in ("GFDL-1.3", "GPL-2", "LGPL-2.1"):
            (self.archive / f"LICENSES/libc6-{name}.txt").write_text(name)
        self.mapping.write_text(self.mapping.read_text() + "libc6\tlib/glibc/libc.so.6\n")
        result = self.write_inventory()
        self.assertEqual(result.returncode, 0, result.stderr)
        components = json.loads((self.archive / "LICENSES/inventory.json").read_text())["components"]
        glibc = next(entry for entry in components if entry.get("package") == "libc6")
        self.assertEqual(glibc["source_package"], "glibc")
        self.assertEqual(glibc["source_version"], "1.2.3-4ubuntu5")
        self.assertEqual(len(glibc["source_urls"]), 3)
        self.assertTrue(all("1.2.3" in url for url in glibc["source_urls"]))
        self.assertEqual(len(glibc["additional_license_files"]), 3)

    def test_static_launcher_records_musl_source_and_license(self):
        (self.archive / "bin/.pg-launcher").write_bytes(b"launcher")
        (self.archive / "LICENSES/musl.copyright").write_text("musl copyright\n")
        self.mapping.write_text(self.mapping.read_text() + "musl\tbin/.pg-launcher\n")
        result = self.write_inventory()
        self.assertEqual(result.returncode, 0, result.stderr)
        components = json.loads((self.archive / "LICENSES/inventory.json").read_text())["components"]
        musl = next(entry for entry in components if entry.get("package") == "musl")
        self.assertEqual(musl["source_package"], "musl")
        self.assertEqual(musl["source_version"], "1.2.3-4ubuntu5")
        self.assertEqual(musl["payload_paths"], ["bin/.pg-launcher"])
        self.assertEqual(len(musl["source_urls"]), 3)


if __name__ == "__main__":
    unittest.main()
