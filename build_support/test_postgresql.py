import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from build_support.postgresql import PATHS_FILE, _copy_dependency_development, _write_pg_config_wrapper, prepare_development


class DevelopmentTests(unittest.TestCase):
    def test_unchanged_pg_config_wrapper_preserves_cargo_input_mtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary)
            (prefix / "bin").mkdir()
            _write_pg_config_wrapper(prefix)
            wrapper = prefix / "bin/pg_config"
            initial = wrapper.stat().st_mtime_ns
            _write_pg_config_wrapper(prefix)
            self.assertEqual(wrapper.stat().st_mtime_ns, initial)
            wrapper.write_text("old wrapper")
            _write_pg_config_wrapper(prefix)
            self.assertTrue(wrapper.read_text().startswith("#!/usr/bin/env python3"))

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


class WindowsDevelopmentTests(unittest.TestCase):
    def test_windows_copy_preserves_native_wrapper_and_relocates_forward_slash_metadata(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            (source / 'bin').mkdir(parents=True)
            (source / 'share').mkdir()
            (source / 'dependencies/lib/pkgconfig').mkdir(parents=True)
            (source / 'bin/pg_config.exe').write_bytes(b'native wrapper')
            (source / 'bin/pg_config.bin.exe').write_bytes(b'upstream executable')
            (source / PATHS_FILE).write_text(json.dumps({'postgresql': r'C:\build\postgresql', 'dependencies': r'C:\build\dependencies\x64-windows'}))
            (source / 'dependencies/lib/pkgconfig/example.pc').write_text('prefix=C:/build/dependencies/x64-windows\n')
            destination = root / 'relocated'
            with patch('build_support.postgresql._write_windows_pg_config_wrapper') as compile_wrapper:
                prepare_development(source, destination)
            compile_wrapper.assert_not_called()
            self.assertEqual((destination / 'bin/pg_config.exe').read_bytes(), b'native wrapper')
            self.assertEqual((destination / 'dependencies/lib/pkgconfig/example.pc').read_text(), f'prefix={destination.resolve()}/dependencies\n')

    def test_windows_packaging_retains_import_libraries_only_in_development_archive(self):
        import tarfile
        from unittest.mock import patch
        from build_support.postgresql import package_postgresql
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            install = root / 'postgresql'
            for directory in ('bin', 'include', 'share/extension', 'lib'):
                (install / directory).mkdir(parents=True)
            for name in ('bin/pg_config.exe', 'bin/postgres.exe', 'include/postgres.h', 'share/extension/plpgsql.control', 'lib/postgres.lib', 'lib/plpgsql.dll'):
                (install / name).write_bytes(name.encode())
            with patch('build_support.postgresql.built_version', return_value='18.6'), patch('build_support.postgresql._bundle_windows'), patch('build_support.postgresql._write_windows_pg_config_wrapper'):
                record = package_postgresql(root, 'windows-x86_64', root / 'dist')
            with tarfile.open(root / 'dist' / record['archive']['filename']) as archive:
                names = archive.getnames()
                self.assertIn('postgresql/bin/postgres.exe', names)
                self.assertNotIn('postgresql/bin/pg_config.exe', names)
                self.assertNotIn('postgresql/lib/postgres.lib', names)
            with tarfile.open(root / 'dist' / record['development_archive']['filename']) as archive:
                names = archive.getnames()
                self.assertIn('postgresql/bin/pg_config.bin.exe', names)
                self.assertIn('postgresql/lib/postgres.lib', names)
