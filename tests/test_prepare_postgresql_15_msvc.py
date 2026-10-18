from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.windows.prepare_postgresql_15_msvc import stage


class PostgreSQL15MsvcDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.installed = self.root / "vcpkg" / "installed" / "x64-windows"
        (self.installed / "include" / "sample").mkdir(parents=True)
        (self.installed / "include" / "sample" / "dep.h").write_text("header", encoding="ascii")
        (self.installed / "lib").mkdir()
        (self.installed / "bin").mkdir()
        libraries = (
            "icuin.lib", "icuuc.lib", "icudt.lib", "lz4.lib", "zstd.lib",
            "zlib.lib", "libssl.lib", "libcrypto.lib", "libxml2.lib", "libxslt.lib",
        )
        for name in libraries:
            (self.installed / "lib" / name).write_bytes(name.encode("ascii"))
        for name in (
            "icuuc77.dll", "lz4.dll", "zstd.dll", "zlib1.dll", "libssl-3-x64.dll",
            "libcrypto-3-x64.dll", "libxml2.dll", "libxslt.dll",
        ):
            (self.installed / "bin" / name).write_bytes(name.encode("ascii"))
        openssl_tool = self.installed / "tools" / "openssl" / "openssl.exe"
        openssl_tool.parent.mkdir(parents=True)
        openssl_tool.write_bytes(b"openssl cli")
        self.staging = self.root / "staged"
        self.config = self.root / "source" / "src" / "tools" / "msvc" / "config.pl"

    def tearDown(self):
        self.temp.cleanup()

    def test_stages_expected_names_and_configuration_without_changing_inputs(self):
        roots = stage(self.root / "vcpkg", self.staging, self.config)

        self.assertEqual(set(roots), {"icu", "lz4", "zstd", "zlib", "openssl", "xml", "xslt"})
        for dependency, library_names in {
            "icu": ("lib64/icuin.lib", "lib64/icuuc.lib", "lib64/icudt.lib"),
            "lz4": ("lib/liblz4.lib",),
            "zstd": ("lib/libzstd.lib",),
            "zlib": ("lib/zdll.lib",),
            "openssl": ("lib/libssl.lib", "lib/libcrypto.lib"),
            "xml": ("lib/libxml2.lib",),
            "xslt": ("lib/libxslt.lib",),
        }.items():
            for library in library_names:
                staged = Path(roots[dependency]) / library
                self.assertTrue(staged.is_file(), staged)
                original_name = staged.name.replace("liblz4", "lz4").replace("libzstd", "zstd").replace("zdll", "zlib")
                original = self.installed / "lib" / original_name
                self.assertEqual(staged.read_bytes(), original.read_bytes())
            self.assertEqual((Path(roots[dependency]) / "include/sample/dep.h").read_text(encoding="ascii"), "header")

        config = self.config.read_text(encoding="ascii")
        self.assertIn("ldap => 0", config)
        self.assertIn("uuid => undef", config)
        self.assertIn("icu =>", config)
        self.assertIn("xslt =>", config)
        self.assertEqual((self.staging / "openssl/bin/openssl.exe").read_bytes(), b"openssl cli")
        self.assertEqual((self.installed / "lib/lz4.lib").read_bytes(), b"lz4.lib")

    def test_fails_when_a_required_import_library_is_missing(self):
        (self.installed / "lib/libcrypto.lib").unlink()
        with self.assertRaisesRegex(RuntimeError, "openssl import library"):
            stage(self.root / "vcpkg", self.staging, self.config)

    def test_stages_zlib_132_cmake_library_names_for_upstream_msvc_layout(self):
        (self.installed / "lib/zlib.lib").unlink()
        (self.installed / "lib/z.lib").write_bytes(b"zlib 1.3.2 import library")
        (self.installed / "bin/zlib1.dll").unlink()
        (self.installed / "bin/z.dll").write_bytes(b"zlib 1.3.2 runtime")

        roots = stage(self.root / "vcpkg", self.staging, self.config)

        self.assertEqual((Path(roots["zlib"]) / "lib/zdll.lib").read_bytes(), b"zlib 1.3.2 import library")

    def test_refuses_to_overwrite_an_existing_msvc_configuration(self):
        self.config.parent.mkdir(parents=True)
        self.config.write_text("user config", encoding="ascii")
        with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
            stage(self.root / "vcpkg", self.staging, self.config)

    def test_requires_the_vcpkg_openssl_cli_for_version_detection(self):
        (self.installed / "tools/openssl/openssl.exe").unlink()
        with self.assertRaisesRegex(RuntimeError, "install openssl\[tools\]"):
            stage(self.root / "vcpkg", self.staging, self.config)


if __name__ == "__main__":
    unittest.main()
