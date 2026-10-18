from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.package_windows_postgresql_test_fixtures import exclude_test_extensions


class WindowsPostgreSQLTestFixturePackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "postgresql"
        self.tests = self.source / "src/test/modules/test_ext1"
        self.tests.mkdir(parents=True)
        (self.tests / "Makefile").write_text("MODULE_big = test_ext1\nEXTENSION = test_ext1\n", encoding="utf-8")
        self.contrib = self.source / "contrib"
        self.contrib.mkdir()
        hstore = self.contrib / "hstore"
        hstore.mkdir()
        (hstore / "Makefile").write_text("MODULE_big = hstore\n", encoding="utf-8")
        msvc = self.source / "src/tools/msvc"
        msvc.mkdir(parents=True)
        (msvc / "Mkvcbuild.pm").write_text("$solution->AddProject('pgoutput', 'dll');\n", encoding="utf-8")
        conversion = self.source / "src/backend/utils/mb/conversion_procs"
        conversion.mkdir(parents=True)
        (conversion / "Makefile").write_text("SUBDIRS = utf8_and_ascii\n", encoding="utf-8")
        self.install = self.root / "install"
        self.extensions = self.install / "share/extension"
        self.extensions.mkdir(parents=True)
        self.lib = self.install / "lib"
        self.lib.mkdir()
        self._file(self.tests / "test_ext1.control", "module")
        self._file(self.extensions / "test_ext1.control", "module")
        self._file(self.extensions / "test_ext1--1.0.sql", "fixture")
        self._file(self.contrib / "hstore.control", "ordinary")
        self._file(self.extensions / "hstore.control", "ordinary")
        self._file(self.extensions / "hstore--1.0.sql", "ordinary sql")
        self._file(self.lib / "test_ext1.dll", "test module")
        self._file(self.lib / "hstore.dll", "ordinary module")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _file(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_excludes_only_source_derived_test_extension_files(self):
        report = exclude_test_extensions(self.source, self.install)

        self.assertEqual(report["extension_names"], ["test_ext1"])
        self.assertEqual(report["native_modules"], ["test_ext1"])
        self.assertEqual(report["excluded_files"], [
            "lib/test_ext1.dll",
            "share/extension/test_ext1--1.0.sql",
            "share/extension/test_ext1.control",
        ])
        self.assertFalse((self.extensions / "test_ext1.control").exists())
        self.assertFalse((self.lib / "test_ext1.dll").exists())
        self.assertTrue((self.extensions / "hstore.control").is_file())
        self.assertTrue((self.extensions / "hstore--1.0.sql").is_file())
        self.assertTrue((self.lib / "hstore.dll").is_file())

    def test_collision_with_contrib_fails_before_removing_anything(self):
        self._file(self.contrib / "test_ext1.control", "contrib collision")

        with self.assertRaisesRegex(RuntimeError, "collides with ordinary contrib"):
            exclude_test_extensions(self.source, self.install)

        self.assertTrue((self.extensions / "test_ext1.control").is_file())
        self.assertTrue((self.extensions / "test_ext1--1.0.sql").is_file())

    def test_fails_closed_when_no_test_extension_is_installed(self):
        (self.extensions / "test_ext1.control").unlink()

        with self.assertRaisesRegex(RuntimeError, "No installed PostgreSQL test-module"):
            exclude_test_extensions(self.source, self.install)

    def test_duplicate_source_extension_names_fail_before_removal(self):
        self._file(self.source / "src/test/modules/second/test_ext1.control", "duplicate")

        with self.assertRaisesRegex(RuntimeError, "Duplicate test-module extension name"):
            exclude_test_extensions(self.source, self.install)

        self.assertTrue((self.extensions / "test_ext1.control").is_file())

    def test_core_dll_collision_fails_before_removing_anything(self):
        (self.source / "src/tools/msvc/Mkvcbuild.pm").write_text(
            "$solution->AddProject('test_ext1', 'dll');\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(RuntimeError, "collides with ordinary PostgreSQL output"):
            exclude_test_extensions(self.source, self.install)

        self.assertTrue((self.lib / "test_ext1.dll").is_file())

    def test_contrib_dll_collision_fails_before_removing_anything(self):
        (self.tests / "Makefile").write_text(
            "MODULE_big = hstore\nEXTENSION = test_ext1\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(RuntimeError, "collides with ordinary PostgreSQL output"):
            exclude_test_extensions(self.source, self.install)

        self.assertTrue((self.lib / "test_ext1.dll").is_file())


if __name__ == "__main__":
    unittest.main()
