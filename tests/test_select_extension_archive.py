import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "select_extension_archive", Path(__file__).resolve().parents[1] / "tools" / "select_extension_archive.py")
selector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(selector)


class SelectExtensionArchiveTests(unittest.TestCase):
    def setUp(self):
        self.support = {"extensions": {"Example Project": {
            "sql_names": ["example", "example_data"],
            "versions": {"2.0": {}, "2.1": {}}}}}
        downloads_20 = [
            {"postgresql_support": {"from": "15.9", "to": "15.10"},
             "url": "https://example.test/exact.tar.gz", "sha256": "a" * 64},
            {"postgresql_support": {"from": "15.11", "to": "16.1"},
             "url": "https://example.test/later.tar.gz", "sha256": "b" * 64},
        ]
        downloads_21 = [{"postgresql_support": {"from": "15.9", "to": "15.10"},
                         "url": "https://example.test/version-2.1.tar.gz", "sha256": "d" * 64}]
        self.inventory = {"schema_version": 1, "extensions": {"example": {
            "2.0": {"downloads": {"linux-x86_64": downloads_20}},
            "2.1": {"downloads": {"linux-x86_64": downloads_21}}}}}

    def select(self, pg="15.10", platform="linux-x86_64", project="Example Project",
               version="2.0", sql="example"):
        return selector.select_archive(self.inventory, self.support, pg, platform,
                                       project, version, sql)

    def test_selects_unique_archive_covering_exact_minor(self):
        self.assertEqual(self.select()["url"], "https://example.test/exact.tar.gz")
        self.assertEqual(self.select("15.11")["url"], "https://example.test/later.tar.gz")

    def test_selected_extension_version_disambiguates_sql_name(self):
        self.assertEqual(self.select(version="2.0")["url"], "https://example.test/exact.tar.gz")
        self.assertEqual(self.select(version="2.1")["url"], "https://example.test/version-2.1.tar.gz")

    def test_version_comparison_does_not_confuse_15_10_with_15_1(self):
        self.assertEqual(self.select("15.10")["url"], "https://example.test/exact.tar.gz")
        with self.assertRaisesRegex(selector.SelectionError, "no archive covering"):
            self.select("15.1")

    def test_missing_out_of_range_and_invalid_project_mapping_fail(self):
        with self.assertRaisesRegex(selector.SelectionError, "no archive covering"):
            self.select("17.1")
        with self.assertRaisesRegex(selector.SelectionError, "no archive"):
            self.select(platform="macos-arm64")
        with self.assertRaisesRegex(selector.SelectionError, "not declared"):
            self.select(version="9.9")
        with self.assertRaisesRegex(selector.SelectionError, "not declared"):
            self.select(sql="wrong_name")

    def test_overlapping_matching_ranges_fail_as_ambiguous(self):
        self.inventory["extensions"]["example"]["2.0"]["downloads"]["linux-x86_64"].append(
            {"postgresql_support": {"from": "15.10", "to": "15.12"},
             "url": "https://example.test/ambiguous.tar.gz", "sha256": "c" * 64})
        with self.assertRaisesRegex(selector.SelectionError, "ambiguous"):
            self.select()


if __name__ == "__main__":
    unittest.main()
