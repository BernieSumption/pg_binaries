import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "plan_work", Path(__file__).resolve().parents[1] / "tools" / "plan_work.py")
plan_work = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan_work)


class PlanWorkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.support = {
            "schema_version": 1,
            "postgresql": {"minimum_major": 15, "stable_release_cutoff": "2025-09-25"},
            "os_support": {name: {"minimum_version": "1"}
                           for name in ("macos", "windows", "linux")},
            "architectures": ["x86_64", "arm64"],
            "extensions": {"Example": {"sql_names": ["example"], "versions": {
                "1.0": {"postgresql_minimum_major": 15}}}},
        }
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "releases": [{"version": "15.9", "release_date": "2025-09-25"}]}
        self.write("support.json", self.support)
        self.write("support/postgresql-releases.json", snapshot)
        self.write("inventory.json", {"postgresql": {}, "extensions": {}})
        self.root.joinpath("policies/extensions.md").parent.mkdir(parents=True, exist_ok=True)
        self.root.joinpath("policies/extensions.md").write_text(
            "## Example — include\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_missing_archives_are_builds_and_unverified_downloads_are_checks(self):
        checksum = "a" * 64
        platform = "linux-x86_64"
        inventory = {
            "postgresql": {"15.9": {"downloads": {platform: {
                "url": "https://example.test/postgres.tgz", "sha256": checksum}}}},
            "extensions": {"example": {"1.0": {"downloads": {platform: [{
                "postgresql_support": {"from": "15.0", "to": "15.9"},
                "url": "https://example.test/ext.tgz", "sha256": checksum}]}}}},
        }
        self.write("inventory.json", inventory)
        result = plan_work.plan(self.root)
        self.assertEqual(result["build_missing"]["core"], [
            ["15.9", "linux-arm64"], ["15.9", "macos-arm64"],
            ["15.9", "macos-x86_64"], ["15.9", "windows-arm64"],
            ["15.9", "windows-x86_64"]])
        self.assertEqual(result["verify_downloaded"]["core"], [["15.9", platform]])
        self.assertEqual(result["build_missing"]["extensions"], [
            ["example", "1.0", "15.9", p] for p in
            ("linux-arm64", "macos-arm64", "macos-x86_64", "windows-arm64", "windows-x86_64")])
        self.assertEqual(result["verify_downloaded"]["extensions"], [
            ["example", "1.0", "15.9", platform]])

    def test_passed_matching_records_remove_downloaded_work(self):
        checksum = "b" * 64
        platform = "linux-x86_64"
        self.write("inventory.json", {"postgresql": {"15.9": {"downloads": {platform: {
            "url": "https://example.test/postgres.tgz", "sha256": checksum}}}},
            "extensions": {}})
        records_dir = self.root / "support/verification"
        records_dir.mkdir(parents=True)
        for endpoint in ("minimum", "current"):
            record = {"schema_version": 1, "outcome": "passed", "sha256": checksum, "component": "postgresql",
                      "version": "15.9", "platform": platform, "postgresql_version": "15.9",
                      "test_revision": "abc", "test_cases": ["smoke"],
                      "environment": {"os": "linux", "architecture": "x86_64",
                                      "os_version": "1" if endpoint == "minimum" else "2", "clean_system": True,
                                      "endpoint": endpoint}}
            (records_dir / f"{endpoint}.json").write_text(json.dumps(record), encoding="utf-8")
        result = plan_work.plan(self.root)
        self.assertNotIn(["15.9", platform], result["verify_downloaded"]["core"])

    def test_output_is_stable(self):
        first = plan_work.plan(self.root)
        second = plan_work.plan(self.root)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_linux_pilot_selects_declared_missing_seventeen_and_eighteen_targets(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "releases": [{"version": "17.11", "release_date": "2025-09-25"},
                                 {"version": "18.0", "release_date": "2025-09-25"}]}
        self.write("support/postgresql-releases.json", snapshot)
        self.assertEqual(plan_work.select_linux_pilot(self.root, "17.11"), {
            "postgresql_version": "17.11", "platform": "linux-x86_64",
            "work": "build_missing", "snapshot_as_of": "2026-01-01"})
        self.assertEqual(plan_work.select_linux_pilot(self.root, "18.0"), {
            "postgresql_version": "18.0", "platform": "linux-x86_64",
            "work": "build_missing", "snapshot_as_of": "2026-01-01"})
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "17 and 18 minors"):
            plan_work.select_linux_pilot(self.root, "15.9")
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "not a missing declared"):
            plan_work.select_linux_pilot(self.root, "18.9")

    def test_linux_pilot_rejects_existing_public_download(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "releases": [{"version": "17.11", "release_date": "2025-09-25"}]}
        self.write("support/postgresql-releases.json", snapshot)
        self.write("inventory.json", {"postgresql": {"17.11": {"downloads": {
            "linux-x86_64": {"url": "https://example.test/pg.tgz", "sha256": "a" * 64}}}},
            "extensions": {}})
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "not a missing declared"):
            plan_work.select_linux_pilot(self.root, "17.11")


if __name__ == "__main__":
    unittest.main()
