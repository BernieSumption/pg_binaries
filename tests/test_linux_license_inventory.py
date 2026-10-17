import importlib.util
import hashlib
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
        dpkg_query.write_text(
            "#!/bin/sh\ncase \"$3\" in\n"
            "  libc6) source=glibc ;;\n  musl) source=musl ;;\n"
            "  libicu70) printf '70.1-2\\ticu\\t70.1-2\\n'; exit 0 ;;\n"
            "  libxml2) printf '2.9.13+dfsg-1ubuntu0.14\\tlibxml2\\t2.9.13+dfsg-1ubuntu0.14\\n'; exit 0 ;;\n"
            "  libssl3) printf '3.0.2-0ubuntu1.30\\topenssl\\t3.0.2-0ubuntu1.30\\n'; exit 0 ;;\n"
            "  *) source=libexample ;;\nesac\n"
            "printf '1.2.3-4ubuntu5\\t%s\\t1.2.3-4ubuntu5\\n' \"$source\"\n"
        )
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
        self.assertEqual(runtime["source_package"], "libexample")
        self.assertEqual(runtime["source_version"], "1.2.3-4ubuntu5")
        self.assertEqual(runtime["payload_paths"], ["lib/runtime/libexample.so"])
        self.assertTrue(runtime["license_source"].startswith("https://"))
        self.assertNotIn("source_urls", runtime)

    def test_rejects_missing_source_package_or_source_version(self):
        dpkg_query = self.root / "bin/dpkg-query"
        for output, message in (
                ("1.2.3-4ubuntu5\\t\\t1.2.3-4ubuntu5\\n", "missing source package name"),
                ("1.2.3-4ubuntu5\\tlibexample\\t\\n", "missing source package version")):
            with self.subTest(message=message):
                dpkg_query.write_text(f"#!/bin/sh\nprintf '{output}'\n")
                result = self.write_inventory()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

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

    def test_rejects_unexpected_glibc_source_package(self):
        (self.archive / "lib/glibc").mkdir()
        (self.archive / "lib/glibc/libc.so.6").write_bytes(b"glibc")
        (self.archive / "LICENSES/libc6.copyright").write_text("glibc copyright\n")
        self.mapping.write_text(self.mapping.read_text() + "libc6\tlib/glibc/libc.so.6\n")
        (self.root / "bin/dpkg-query").write_text(
            "#!/bin/sh\nprintf '1.2.3-4ubuntu5\\tunexpected\\t1.2.3-4ubuntu5\\n'\n"
        )
        result = self.write_inventory()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected libc6 source package", result.stderr)

    def add_icu(self, metadata="70.1-2\\ticu\\t70.1-2"):
        (self.archive / "lib/runtime/libicuuc.so.70").write_bytes(b"icu")
        (self.archive / "LICENSES/libicu70.copyright").write_text("Ubuntu ICU copyright\n")
        notice = REPO / "support/licences/icu-70.1-LICENSE.txt"
        (self.archive / "LICENSES/libicu70-icu-70.1-LICENSE.txt").write_bytes(notice.read_bytes())
        self.mapping.write_text(
            self.mapping.read_text() + "libicu70\tlib/runtime/libicuuc.so.70\n"
        )
        (self.root / "bin/dpkg-query").write_text(
            "#!/bin/sh\ncase \"$3\" in\n"
            f"  libicu70) printf '{metadata}\\n'; exit 0 ;;\n"
            "  libc6) source=glibc ;;\n  musl) source=musl ;;\n"
            "  *) source=libexample ;;\nesac\n"
            "printf '1.2.3-4ubuntu5\\t%s\\t1.2.3-4ubuntu5\\n' \"$source\"\n"
        )
        (self.root / "bin/dpkg-query").chmod(0o755)

    def test_icu_inventory_includes_hash_checked_upstream_third_party_notices(self):
        self.add_icu()
        result = self.write_inventory()
        self.assertEqual(result.returncode, 0, result.stderr)
        components = json.loads((self.archive / "LICENSES/inventory.json").read_text())["components"]
        icu = next(entry for entry in components if entry.get("package") == "libicu70")
        self.assertEqual((icu["version"], icu["source_package"], icu["source_version"]),
                         ("70.1-2", "icu", "70.1-2"))
        notice = "libicu70-icu-70.1-LICENSE.txt"
        self.assertEqual(icu["additional_license_files"], [notice])
        self.assertEqual(
            hashlib.sha256((self.archive / "LICENSES" / notice).read_bytes()).hexdigest(),
            "861671f8c712aa046f8f5ac89239e6c33821636516c5d0cc8c4e1973085f27a6",
        )
        ordinary = next(entry for entry in components if entry.get("package") == "libexample1")
        self.assertNotIn("additional_license_files", ordinary)

    def test_icu_notice_requires_exact_binary_and_source_versions(self):
        for metadata in ("70.1-3\\ticu\\t70.1-2", "70.1-2\\ticu\\t70.1-3",
                         "70.1-2\\tother\\t70.1-2"):
            with self.subTest(metadata=metadata):
                self.add_icu(metadata)
                result = self.write_inventory()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unexpected libicu70 source identity", result.stderr)

    def test_icu_notice_must_match_pinned_upstream_text(self):
        self.add_icu()
        (self.archive / "LICENSES/libicu70-icu-70.1-LICENSE.txt").write_text("stale notice")
        result = self.write_inventory()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected ICU third-party notices", result.stderr)

    def add_libxml2(self, metadata="2.9.13+dfsg-1ubuntu0.14\tlibxml2\t2.9.13+dfsg-1ubuntu0.14"):
        (self.archive / "lib/runtime/libxml2.so.2").write_bytes(b"libxml2")
        (self.archive / "LICENSES/libxml2.copyright").write_text("Ubuntu libxml2 copyright\n")
        notice = REPO / "support/licences/libxml2-2.9.13-dict-notice.txt"
        (self.archive / "LICENSES" / notice.name).write_bytes(notice.read_bytes())
        self.mapping.write_text(
            self.mapping.read_text() + "libxml2\tlib/runtime/libxml2.so.2\n"
        )
        (self.root / "bin/dpkg-query").write_text(
            "#!/bin/sh\ncase \"$3\" in\n"
            f"  libxml2) printf '{metadata}\n'; exit 0 ;;\n"
            "  libc6) source=glibc ;;\n  musl) source=musl ;;\n"
            "  *) source=libexample ;;\nesac\n"
            "printf '1.2.3-4ubuntu5\t%s\t1.2.3-4ubuntu5\n' \"$source\"\n"
        )
        (self.root / "bin/dpkg-query").chmod(0o755)

    def test_libxml2_inventory_includes_hash_checked_dict_notice_for_exact_package(self):
        self.add_libxml2()
        result = self.write_inventory()
        self.assertEqual(result.returncode, 0, result.stderr)
        components = json.loads((self.archive / "LICENSES/inventory.json").read_text())["components"]
        xml = next(entry for entry in components if entry.get("package") == "libxml2")
        notice = "libxml2-2.9.13-dict-notice.txt"
        self.assertEqual((xml["version"], xml["source_package"], xml["source_version"]),
                         ("2.9.13+dfsg-1ubuntu0.14", "libxml2", "2.9.13+dfsg-1ubuntu0.14"))
        self.assertEqual(xml["additional_license_files"], [notice])
        self.assertEqual(
            hashlib.sha256((self.archive / "LICENSES" / notice).read_bytes()).hexdigest(),
            "5e67dfcf4fbeb9e1a224e1001ad7cd4cab6cadb7383cc173ccd09315f89b0d9a",
        )

    def test_libxml2_notice_requires_exact_identity_and_text(self):
        for metadata, changed_notice in (
                ("2.9.13+dfsg-1ubuntu0.15\tlibxml2\t2.9.13+dfsg-1ubuntu0.14", False),
                ("2.9.13+dfsg-1ubuntu0.14\tother\t2.9.13+dfsg-1ubuntu0.14", False),
                ("2.9.13+dfsg-1ubuntu0.14\tlibxml2\t2.9.13+dfsg-1ubuntu0.14", True)):
            with self.subTest(metadata=metadata, changed_notice=changed_notice):
                self.add_libxml2(metadata)
                if changed_notice:
                    (self.archive / "LICENSES/libxml2-2.9.13-dict-notice.txt").write_text("stale")
                result = self.write_inventory()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unexpected libxml2 dict.c notice" if changed_notice
                              else "unexpected libxml2 source identity", result.stderr)

    def add_openssl(self, metadata="3.0.2-0ubuntu1.30\topenssl\t3.0.2-0ubuntu1.30"):
        (self.archive / "lib/runtime/libssl.so.3").write_bytes(b"openssl")
        (self.archive / "LICENSES/libssl3.copyright").write_text(
            "OpenSSL copyright and Apache-2.0 reference\n")
        (self.archive / "LICENSES/common-licenses/Apache-2.0").parent.mkdir(
            parents=True, exist_ok=True)
        (self.archive / "LICENSES/common-licenses/Apache-2.0").write_text(
            "Apache License\nVersion 2.0\n")
        self.mapping.write_text(
            self.mapping.read_text() + "libssl3\tlib/runtime/libssl.so.3\n"
        )
        (self.root / "bin/dpkg-query").write_text(
            "#!/bin/sh\ncase \"$3\" in\n"
            f"  libssl3) printf '{metadata}\n'; exit 0 ;;\n"
            "  libc6) source=glibc ;;\n  musl) source=musl ;;\n"
            "  *) source=libexample ;;\nesac\n"
            "printf '1.2.3-4ubuntu5\t%s\t1.2.3-4ubuntu5\n' \"$source\"\n"
        )
        (self.root / "bin/dpkg-query").chmod(0o755)

    def test_openssl_inventory_includes_common_apache_license_for_exact_package(self):
        self.add_openssl()
        result = self.write_inventory()
        self.assertEqual(result.returncode, 0, result.stderr)
        components = json.loads((self.archive / "LICENSES/inventory.json").read_text())["components"]
        openssl = next(entry for entry in components if entry.get("package") == "libssl3")
        self.assertEqual((openssl["version"], openssl["source_package"],
                          openssl["source_version"]),
                         ("3.0.2-0ubuntu1.30", "openssl", "3.0.2-0ubuntu1.30"))
        self.assertEqual(openssl["additional_license_files"],
                         ["common-licenses/Apache-2.0"])

    def test_openssl_additional_license_requires_exact_identity_and_nonempty_text(self):
        for metadata, missing_license in (
                ("3.0.2-0ubuntu1.31\topenssl\t3.0.2-0ubuntu1.30", False),
                ("3.0.2-0ubuntu1.30\topenssl\t3.0.2-0ubuntu1.31", False),
                ("3.0.2-0ubuntu1.30\tother\t3.0.2-0ubuntu1.30", False),
                ("3.0.2-0ubuntu1.30\topenssl\t3.0.2-0ubuntu1.30", True)):
            with self.subTest(metadata=metadata, missing_license=missing_license):
                self.add_openssl(metadata)
                if missing_license:
                    (self.archive / "LICENSES/common-licenses/Apache-2.0").write_text("")
                result = self.write_inventory()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("missing OpenSSL Apache-2.0 license text" if missing_license
                              else "unexpected libssl3 source identity", result.stderr)

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
