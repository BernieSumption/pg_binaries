import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from build_support.postgresql import PATHS_FILE, _copy_dependency_development, prepare_development


class DevelopmentTests(unittest.TestCase):
    def test_dependency_development_files_exclude_build_tools(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "dependencies"
            for name in ("include", "lib/pkgconfig", "bin", "share/doc"):
                (source / name).mkdir(parents=True, exist_ok=True)
            for name in ("include/example.h", "lib/libexample.dylib", "lib/pkgconfig/example.pc", "bin/xml2-config", "bin/makeconv", "share/doc/readme"):
                (source / name).write_text(name)
            destination = root / "development"
            _copy_dependency_development(source, destination)
            self.assertTrue((destination / "include/example.h").is_file())
            self.assertTrue((destination / "lib/pkgconfig/example.pc").is_file())
            self.assertTrue((destination / "bin/xml2-config").is_file())
            self.assertFalse((destination / "bin/makeconv").exists())
            self.assertFalse((destination / "share").exists())

    def test_rejects_copy_inside_its_own_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary).resolve()
            with self.assertRaisesRegex(ValueError, "must not overlap"):
                prepare_development(source, source / "private")

    def test_relocates_pgxs_config_and_pg_config_flags_without_changing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source/postgresql"
            (source / "bin").mkdir(parents=True)
            (source / "share").mkdir()
            (source / "lib/pgxs/src").mkdir(parents=True)
            (source / "dependencies/lib/pkgconfig").mkdir(parents=True)
            paths = {"postgresql": "/original/postgresql", "dependencies": "/original/dependencies"}
            (source / PATHS_FILE).write_text(json.dumps(paths))
            flags = "-I/original/dependencies/include -L/original/postgresql/lib"
            binary = source / "bin/pg_config.bin"
            binary.write_text("#!/bin/sh\nprintf '%s\\n' '" + flags + "'\n")
            binary.chmod(0o755)
            makefile = source / "lib/pgxs/src/Makefile.global"
            makefile.write_text("prefix = /original/postgresql\nCPPFLAGS = -I/original/dependencies/include\n")
            pc = source / "dependencies/lib/pkgconfig/example.pc"
            pc.write_text("prefix=/original/dependencies\n")
            destination = root / "new location/postgresql"
            prepare_development(source, destination)
            output = subprocess.check_output([str(destination / "bin/pg_config"), "--cppflags"], text=True)
            self.assertEqual(output.strip(), f"-I{destination}/dependencies/include -L{destination}/lib")
            self.assertIn(str(destination), (destination / "lib/pgxs/src/Makefile.global").read_text())
            self.assertEqual((destination / "dependencies/lib/pkgconfig/example.pc").read_text(), f"prefix={destination}/dependencies\n")
            self.assertIn("/original/postgresql", makefile.read_text())
            # A second private copy must not retain paths into the first one.
            second = root / "second/postgresql"
            prepare_development(destination, second)
            self.assertNotIn(str(destination), (second / "lib/pgxs/src/Makefile.global").read_text())
            self.assertIn(str(second), (second / "lib/pgxs/src/Makefile.global").read_text())

    def test_each_copy_is_writable_without_modifying_the_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source"
            (source / "bin").mkdir(parents=True)
            (source / "share").mkdir()
            (source / PATHS_FILE).write_text(json.dumps({"postgresql": "/old/postgresql", "dependencies": "/old/dependencies"}))
            (source / "bin/pg_config.bin").write_text("original")
            destination = root / "private"
            prepare_development(source, destination)
            (destination / "bin/pg_config.bin").write_text("changed")
            self.assertEqual((source / "bin/pg_config.bin").read_text(), "original")
