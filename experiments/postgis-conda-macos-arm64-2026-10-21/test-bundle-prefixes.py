import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("bundle.py")
SPEC = importlib.util.spec_from_file_location("postgis_trial_bundle", MODULE_PATH)
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class BundlePrefixTests(unittest.TestCase):
    def test_absolute_and_rpath_search_respects_prefix_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            prefixes = [base / "gdal", base / "conda"]
            libraries = []
            for prefix, content in zip(prefixes, (b"GDAL", b"conda")):
                library = prefix / "lib/libgdal.dylib"
                library.parent.mkdir(parents=True)
                library.write_bytes(content)
                libraries.append(library.resolve())
            bundle.libdir = base / "package/lib"

            with patch.dict(os.environ, {"PG_MACOS_DEPENDENCY_PREFIX": os.pathsep.join(map(str, prefixes))}):
                self.assertEqual(bundle.resolve_dependency("/old/path/libgdal.dylib"), libraries[0])
                self.assertEqual(bundle.resolve_dependency("@rpath/libgdal.dylib"), libraries[0])

            with patch.dict(os.environ, {"PG_MACOS_DEPENDENCY_PREFIX": os.pathsep.join(map(str, reversed(prefixes)))}):
                self.assertEqual(bundle.resolve_dependency("/old/path/libgdal.dylib"), libraries[1])
                self.assertEqual(bundle.resolve_dependency("@rpath/libgdal.dylib"), libraries[1])

    def test_prefix_symlinks_cannot_escape_their_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            prefix = base / "gdal"
            library = prefix / "lib/libexternal.dylib"
            outside = base / "external.dylib"
            library.parent.mkdir(parents=True)
            outside.write_bytes(b"external")
            library.symlink_to(outside)
            bundle.libdir = base / "package/lib"

            with patch.dict(os.environ, {"PG_MACOS_DEPENDENCY_PREFIX": str(prefix)}):
                self.assertIsNone(bundle.resolve_dependency("@rpath/libexternal.dylib"))
                self.assertIsNone(bundle.resolve_dependency(str(library)))


if __name__ == "__main__":
    unittest.main()
