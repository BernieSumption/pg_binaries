import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "scripts/macos/bundle.py"
SPEC = importlib.util.spec_from_file_location("macos_bundle", MODULE_PATH)
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class MacosBundleTests(unittest.TestCase):
    def test_resolves_rpath_and_bare_names_from_dependency_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary) / "source-install"
            library = prefix / "lib/libicuuc.77.dylib"
            library.parent.mkdir(parents=True)
            library.write_bytes(b"pinned source build")
            bundle.libdir = Path(temporary) / "package/lib"

            with patch.dict(os.environ, {"PG_MACOS_DEPENDENCY_PREFIX": str(prefix)}):
                self.assertEqual(bundle.resolve_dependency("@rpath/libicuuc.77.dylib"), library.resolve())
                self.assertEqual(bundle.resolve_dependency("libicuuc.77.dylib"), library.resolve())

    def test_prefix_resolution_does_not_follow_links_outside_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            prefix = base / "prefix"
            external = base / "external.dylib"
            (prefix / "lib").mkdir(parents=True)
            external.write_bytes(b"outside")
            (prefix / "lib/libexample.dylib").symlink_to(external)
            bundle.libdir = base / "package/lib"

            with patch.dict(os.environ, {"PG_MACOS_DEPENDENCY_PREFIX": str(prefix)}):
                self.assertIsNone(bundle.resolve_dependency("@rpath/libexample.dylib"))
                self.assertIsNone(bundle.resolve_dependency("libexample.dylib"))

    def test_absolute_dependencies_stay_absolute_and_bare_names_do_not_search_host(self):
        bundle.libdir = Path("/package/lib")
        absolute = Path("/opt/elsewhere/libsample.dylib")
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, "glob") as glob:
            self.assertEqual(bundle.resolve_dependency(str(absolute)), absolute)
            self.assertIsNone(bundle.resolve_dependency("libsample.dylib"))
            glob.assert_not_called()

    def test_absolute_source_install_name_uses_pinned_library(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary) / "source-install"
            library = prefix / "lib/liblz4.1.dylib"
            library.parent.mkdir(parents=True)
            library.write_bytes(b"pinned source build")
            bundle.libdir = Path(temporary) / "package/lib"

            with patch.dict(os.environ, {"PG_MACOS_DEPENDENCY_PREFIX": str(prefix)}):
                self.assertEqual(
                    bundle.resolve_dependency("/usr/local/lib/liblz4.1.dylib"),
                    library.resolve(),
                )

    def test_homebrew_rpath_lookup_remains_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "libsample.dylib"
            library.write_bytes(b"homebrew")
            bundle.libdir = Path(temporary) / "package/lib"

            def homebrew_glob(path, pattern):
                return [library] if str(path) in ("/usr/local/opt", "/opt/homebrew/opt") else []

            with patch.dict(os.environ, {}, clear=True), patch.object(Path, "glob", homebrew_glob):
                self.assertEqual(bundle.resolve_dependency("@rpath/libsample.dylib"), library.resolve())


if __name__ == "__main__":
    unittest.main()
