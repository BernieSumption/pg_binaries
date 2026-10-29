import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from platforms.macos.bundle import dependencies, main, prefix_library


class PrefixLibraryTests(unittest.TestCase):
    def test_resolves_bare_library_name_under_dependency_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            library = prefix / "lib" / "libicuuc.78.dylib"
            library.parent.mkdir()
            library.write_bytes(b"library")

            self.assertEqual(prefix_library("libicuuc.78.dylib", prefix), library.resolve())

    def test_rejects_paths_and_files_outside_dependency_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "prefix"
            prefix.mkdir()
            self.assertIsNone(prefix_library("../libicuuc.78.dylib", prefix))
            self.assertIsNone(prefix_library("libicuuc.78.dylib", prefix))
            outside = Path(directory) / "outside.dylib"
            outside.write_bytes(b"outside")
            (prefix / "lib").mkdir()
            (prefix / "lib" / "libicuuc.78.dylib").symlink_to(outside)
            self.assertIsNone(prefix_library("libicuuc.78.dylib", prefix))


class BundleTests(unittest.TestCase):
    def test_text_files_do_not_launch_native_inspection_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            header = Path(directory) / "example.h"
            header.write_text("#include <stdio.h>\n")
            with patch("platforms.macos.bundle.run") as run:
                self.assertIsNone(dependencies(header))
                run.assert_not_called()

    def test_thin_and_universal_headers_still_receive_native_inspection(self):
        for magic in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
            with self.subTest(magic=magic), tempfile.TemporaryDirectory() as directory:
                binary = Path(directory) / "example"
                binary.write_bytes(magic)
                with patch("platforms.macos.bundle.run", return_value=SimpleNamespace(returncode=1)) as run:
                    self.assertIsNone(dependencies(binary))
                    run.assert_called_once_with("lipo", "-archs", str(binary))

    def test_conflicting_absolute_dependencies_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            payload = root / "payload"
            prefix = root / "dependencies"
            (payload / "lib").mkdir(parents=True)
            prefix.mkdir()
            first, second = payload / "lib/first.so", payload / "lib/second.so"
            first.write_bytes(b"first module")
            second.write_bytes(b"second module")
            libraries = []
            for name, data in (("a", b"ABI one"), ("b", b"ABI two")):
                library = root / name / "same.dylib"
                library.parent.mkdir()
                library.write_bytes(data)
                libraries.append(library)
            def dependencies(path):
                if path == first:
                    return [str(libraries[0])]
                if path == second:
                    return [str(libraries[1])]
                return None
            with patch("platforms.macos.bundle.dependencies", side_effect=dependencies):
                with self.assertRaisesRegex(SystemExit, "dependency filename collision"):
                    main([str(payload), str(prefix)])

    def test_reuses_postgresql_library_without_copying_development_files(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            payload = workspace / "payload"
            postgres = workspace / "postgresql"
            prefix = workspace / "build/dependencies"
            (payload / "lib").mkdir(parents=True)
            (postgres / "lib").mkdir(parents=True)
            prefix.mkdir(parents=True)
            module = payload / "lib/example.so"
            module.write_bytes(b"module")
            library = postgres / "lib/libpq.5.dylib"
            library.write_bytes(b"postgres library")
            dependency = [str(library)]
            calls = []

            def run(*args):
                calls.append(args)
                if args[:2] == ("install_name_tool", "-change"):
                    dependency[:] = [args[3]]
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("platforms.macos.bundle.dependencies", side_effect=lambda path: list(dependency)), \
                 patch("platforms.macos.bundle.rpaths", return_value=[]), \
                 patch("platforms.macos.bundle.run", side_effect=run):
                main([str(payload), str(prefix), "--postgresql-prefix", str(postgres)])
            self.assertEqual(dependency, ["@loader_path/libpq.5.dylib"])
            self.assertFalse((payload / "lib/libpq.5.dylib").exists())
            self.assertTrue(any(call[0] == "codesign" for call in calls))


if __name__ == "__main__":
    unittest.main()
