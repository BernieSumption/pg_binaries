import json
from pathlib import Path
import tempfile
import unittest

from verification.inventory import InventoryError, make_inventory


class InventoryDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.support = {
            "targets": {"macos-arm64": {"minimum_os_version": "11.0"}},
            "postgresql": {},
            "packages": {
                "postgis": {
                    "config": {"environment_paths": {"PROJ_DATA": "share/proj"}},
                    "extensions": {
                        "postgis": {},
                        "postgis_tiger_geocoder": {},
                    },
                },
                "pgaudit": {
                    "extensions": {"pgaudit": {"config": {"shared_preload_libraries": ["pgaudit"]}}},
                },
            },
        }

    def report(self, target="macos-arm64", outcomes=None, builtins=None):
        name = f"report-{target}.json"
        default_outcomes = [(name, "passed") for name in self.support["packages"]]
        default_outcomes.extend((("postgresql-only", "passed"), ("all-packages", "passed")))
        report = {
            "target": target,
            "postgresql_version": "18.6",
            "extension_versions": {"postgis": "3.6.4", "postgis_tiger_geocoder": "2025.2", "pgaudit": "18.0"},
            "archives": {
                "postgresql": {"filename": "postgresql-18.6-macos-arm64.tar.gz", "sha256": "a" * 64},
                "postgis": {"filename": "postgis-postgresql-18.6-macos-arm64.tar.gz", "sha256": "b" * 64},
                "pgaudit": {"filename": "pgaudit-postgresql-18.6-macos-arm64.tar.gz", "sha256": "c" * 64},
            },
            "combinations": [{"name": n, "outcome": o} for n, o in (
                outcomes if outcomes is not None else default_outcomes)],
            "postgresql_builtin_extensions": builtins if builtins is not None else ["citext", "hstore"],
        }
        path = self.root / name
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_creates_complete_inventory_using_verified_archives(self):
        result = make_inventory([self.report()], "v18.6", self.support,
                                today="2026-10-27", suffix="0123abcd")
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["inventory_version"], "18.6-2026-10-27-0123abcd")
        self.assertEqual(result["os_support"], {"macos": {"minimum_version": "11.0"}})
        self.assertEqual(result["extensions"]["citext"], {"package": "postgresql"})
        self.assertEqual(result["extensions"]["postgis"]["version"], "3.6.4")
        self.assertEqual(result["extensions"]["postgis_tiger_geocoder"]["version"], "2025.2")
        self.assertEqual(result["extensions"]["pgaudit"]["config"], {"shared_preload_libraries": ["pgaudit"]})
        self.assertEqual(result["packages"]["postgis"]["config"], self.support["packages"]["postgis"]["config"])
        download = result["packages"]["postgresql"]["downloads"]["macos-arm64"]
        self.assertEqual(download["url"], "https://github.com/BernieSumption/pg_binaries/releases/download/v18.6/postgresql-18.6-macos-arm64.tar.gz")
        self.assertEqual(download["sha256"], "a" * 64)

    def test_requires_every_combination_to_pass(self):
        with self.assertRaisesRegex(InventoryError, "every required verification combination"):
            make_inventory([self.report(outcomes=[("all-packages", "failed")])], "tag", self.support)
        with self.assertRaisesRegex(InventoryError, "every required verification combination"):
            make_inventory([self.report(outcomes=[("all-packages", "passed")])], "tag", self.support)

    def test_rejects_unsupported_target_and_missing_archive(self):
        with self.assertRaisesRegex(InventoryError, "unsupported target"):
            make_inventory([self.report("linux-arm64")], "tag", self.support)
        path = self.report()
        data = json.loads(path.read_text())
        del data["archives"]["pgaudit"]
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(InventoryError, "every selected package"):
            make_inventory([path], "tag", self.support)

    def test_rejects_conflicting_os_minima_for_same_os(self):
        self.support["targets"]["macos-x64"] = {"minimum_os_version": "12.0"}
        second = self.report("macos-x64")
        data = json.loads(second.read_text())
        data["archives"] = {key: {**value, "filename": value["filename"].replace("arm64", "x64")}
                             for key, value in data["archives"].items()}
        second.write_text(json.dumps(data))
        with self.assertRaisesRegex(InventoryError, "inconsistent macos minimum"):
            make_inventory([self.report(), second], "tag", self.support)

    def test_requires_every_declared_target(self):
        self.support["targets"]["linux-arm64"] = {"minimum_os_version": "5.15"}
        with self.assertRaisesRegex(InventoryError, "missing verified targets"):
            make_inventory([self.report()], "tag", self.support)

    def test_rejects_different_postgresql_versions_between_targets(self):
        self.support["targets"]["macos-x86_64"] = {"minimum_os_version": "11.0"}
        first, second = self.report(), self.report("macos-x86_64")
        data = json.loads(second.read_text())
        data["postgresql_version"] = "18.7"
        second.write_text(json.dumps(data))
        with self.assertRaisesRegex(InventoryError, "PostgreSQL versions differ"):
            make_inventory([first, second], "tag", self.support)

    def test_rejects_different_sql_versions_between_targets(self):
        self.support["targets"]["macos-x86_64"] = {"minimum_os_version": "11.0"}
        first, second = self.report(), self.report("macos-x86_64")
        data = json.loads(second.read_text())
        for archive in data["archives"].values():
            archive["filename"] = archive["filename"].replace("arm64", "x86_64")
        data["extension_versions"]["postgis"] = "different-sql-version"
        second.write_text(json.dumps(data))
        with self.assertRaisesRegex(InventoryError, "conflicting inventory mapping"):
            make_inventory([first, second], "tag", self.support)

    def test_builtin_target_restriction_matches_verified_archives(self):
        self.support["targets"]["macos-x86_64"] = {"minimum_os_version": "11.0"}
        first = self.report()
        second = self.report("macos-x86_64", builtins=["citext"])
        data = json.loads(second.read_text(encoding="utf-8"))
        for archive in data["archives"].values():
            archive["filename"] = archive["filename"].replace("arm64", "x86_64")
        second.write_text(json.dumps(data), encoding="utf-8")
        inventory = make_inventory([first, second], "tag", self.support)
        self.assertEqual(inventory["extensions"]["citext"], {"package": "postgresql"})
        self.assertEqual(inventory["extensions"]["hstore"], {
            "package": "postgresql", "targets": ["macos-arm64"]})


if __name__ == "__main__":
    unittest.main()
