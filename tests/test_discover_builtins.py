import importlib.util
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "discover_builtins", Path(__file__).resolve().parents[1] / "tools" / "discover_builtins.py"
)
discover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(discover)


class BuiltinDiscoveryTests(unittest.TestCase):
    def test_control_filenames_are_sorted_and_auxiliary_sql_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "share" / "extension"
            directory.mkdir(parents=True)
            for name in ("zeta.control", "citext.control", "hstore.control",
                         "hstore--1.0.sql", "hstore--1.0--1.1.sql"):
                (directory / name).write_text("", encoding="utf-8")

            self.assertEqual(discover.discover_builtins(temporary), ["citext", "hstore", "zeta"])

    def test_missing_or_malformed_extension_directory_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(discover.DiscoveryError, "does not exist"):
                discover.discover_builtins(temporary)

            directory = Path(temporary) / "share" / "extension"
            directory.mkdir(parents=True)
            (directory / "bad name.control").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(discover.DiscoveryError, "malformed"):
                discover.discover_builtins(temporary)

    def test_non_directory_extension_path_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            share = Path(temporary) / "share"
            share.mkdir()
            (share / "extension").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(discover.DiscoveryError, "does not exist"):
                discover.discover_builtins(temporary)


if __name__ == "__main__":
    unittest.main()
