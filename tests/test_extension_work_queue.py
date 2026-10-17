import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "extension_work_queue", Path(__file__).resolve().parents[1] / "tools" / "extension_work_queue.py")
queue_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(queue_tool)


class ExtensionWorkQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.support = {
            "schema_version": 1,
            "version_selection_as_of": "2026-10-17",
            "postgresql": {"minimum_major": 15},
            "os_support": {name: {"minimum_version": "1"} for name in ("macos", "windows", "linux")},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"], "linux": ["x86_64", "arm64"]},
            "extensions": {
                "PostGIS": {"sql_names": ["postgis", "postgis_raster"], "requires": [],
                            "versions": {"3.5.7": {"postgresql_minimum_major": 15, "postgresql_maximum_major": 18},
                                         "3.6.4": {"postgresql_minimum_major": 15, "postgresql_maximum_major": 18}}},
                "PostGIS TIGER Geocoder": {"sql_names": ["postgis_tiger_geocoder"], "requires": ["PostGIS"],
                                            "requires_versions": {"PostGIS": {"minimum_version": "3.6"}},
                                            "versions": {"2025.2": {"postgresql_minimum_major": 16, "postgresql_maximum_major": 18}}},
            },
        }
        self.write("support.json", self.support)
        self.write("support/postgresql-releases.json", {
            "as_of": "2026-10-16", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01", "supported_majors": [16, 18]},
            "releases": [{"version": "16.15", "release_date": "2026-08-13"},
                         {"version": "18.6", "release_date": "2026-08-13"}],
        })
        policy = self.root / "policies/extensions.md"
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text("## PostGIS — include\n## PostGIS TIGER Geocoder — include\n", encoding="utf-8")
        self.write("inventory.json", {"postgresql": {}, "extensions": {}})

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_ids_and_order_are_stable_and_batch_is_bounded(self):
        first = queue_tool.build_queue(self.root)
        second = queue_tool.build_queue(self.root)
        self.assertEqual(first, second)
        batch = queue_tool.select_batch(first, 3)
        self.assertLessEqual(len(batch), 3)
        known = {item["id"] for item in first["work_items"]}
        self.assertTrue(all(dep in known for item in first["work_items"] for dep in item["depends_on"]))
        self.assertEqual(len({item["id"] for item in first["work_items"]}), len(first["work_items"]))

    def test_project_archive_group_has_one_exact_build_and_current_checks(self):
        items = queue_tool.build_queue(self.root)["work_items"]
        postgis = [item for item in items if item.get("project") == "PostGIS" and
                   item.get("version") == "3.6.4" and item.get("platform") == "linux-x86_64" and
                   item.get("postgresql_major") == 18]
        builds = [item for item in postgis if item["kind"] == "build-extension"]
        checks = [item for item in postgis if item["kind"] == "verify-extension"]
        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0]["sql_names"], ["postgis", "postgis_raster"])
        self.assertEqual(builds[0]["postgresql_version"], "18.6")
        self.assertEqual({item["endpoint"] for item in checks}, {"current"})
        self.assertEqual(len(checks), 2)
        self.assertEqual(builds[0]["verification_status"], "unverified")
        self.assertNotIn("postgresql_range", builds[0])
        self.assertNotIn("build_postgresql_version", builds[0])

    def test_candidate_build_uses_latest_minor_and_other_endpoint_is_verified_separately(self):
        snapshot = json.loads((self.root / "support/postgresql-releases.json").read_text())
        self.write("support/postgresql-releases.json", snapshot)
        queue = queue_tool.build_queue(self.root)
        group = next(item for item in queue["work_items"] if item.get("project") == "PostGIS"
                     and item.get("version") == "3.6.4" and item.get("postgresql_major") == 18
                     and item.get("platform") == "linux-x86_64" and item["kind"] == "build-extension")
        self.assertEqual(group["postgresql_version"], "18.6")
        self.assertEqual(group["depends_on"], [queue_tool._id("build-core", "18.6", "linux-x86_64")])
        checks = [item for item in queue["work_items"] if item.get("project") == "PostGIS"
                  and item.get("version") == "3.6.4" and item.get("postgresql_major") == 18
                  and item.get("platform") == "linux-x86_64" and item["kind"] == "verify-extension"]
        self.assertEqual({item["postgresql_version"] for item in checks}, {"18.6"})
        self.assertEqual({item["endpoint"] for item in checks}, {"current"})

    def test_inventory_archive_binding_does_not_claim_endpoint_coverage(self):
        checksum = "d" * 64
        self.write("inventory.json", {"postgresql": {}, "extensions": {
            name: {"3.6.4": {"downloads": {"linux-x86_64": [{
                "postgresql_support": {"from": "18.6", "to": "18.6"},
                "url": "https://example.test/postgis.tar.gz", "sha256": checksum}]}}}
            for name in ("postgis", "postgis_raster")}})
        group = next(item for item in queue_tool.build_queue(self.root)["work_items"]
                     if item.get("project") == "PostGIS" and item.get("postgresql_major") == 18
                     and item.get("platform") == "linux-x86_64" and item.get("version") == "3.6.4"
                     and item["kind"] == "build-extension")
        self.assertEqual(group["status"], "complete")
        self.assertEqual(group["verification_status"], "unverified")

    def test_tiger_dependency_selects_structured_minimum_version_candidate(self):
        items = {item["id"]: item for item in queue_tool.build_queue(self.root)["work_items"]}
        tiger_id = queue_tool._id("build-extension", "PostGIS TIGER Geocoder", "2025.2", "linux-x86_64", 18)
        tiger = items[tiger_id]
        postgis_id = queue_tool._id("build-extension", "PostGIS", "3.6.4", "linux-x86_64", 18)
        self.assertEqual(tiger["status"], "needed")
        self.assertEqual(tiger["depends_on"], sorted([*tiger["depends_on"]]))
        self.assertEqual(items[postgis_id]["sql_names"], ["postgis", "postgis_raster"])
        self.assertIn(postgis_id, tiger["depends_on"])
        self.assertFalse(tiger["blocked_by_unresolved_prerequisite"])
        queue = queue_tool.build_queue(self.root)
        self.assertFalse(any(row["item_id"] == tiger_id for row in queue["unresolved_prerequisites"]))
        self.assertEqual(tiger["postgresql_version"], "18.6")
        self.assertEqual(tiger["verification_status"], "unverified")
        selected = queue_tool.select_batch(queue, 100, "PostGIS TIGER Geocoder", "linux-x86_64")["selected_items"]
        selected_ids = [item["id"] for item in selected]
        self.assertIn(tiger_id, selected_ids)
        self.assertLess(selected_ids.index(postgis_id), selected_ids.index(tiger_id))
        self.assertTrue(all(set(item["depends_on"]) <= set(selected_ids[:index])
                            for index, item in enumerate(selected)
                            if item["status"] != "complete"))

    def test_retained_evidence_is_reported_without_satisfying_missing_inventory(self):
        self.write("support/verification-profiles.json", {"schema_version": 1, "profiles": {
            "old": {"scope": "pilot-smoke", "platforms": ["linux-x86_64"],
                    "case_ids": ["case-a"], "sources": ["tests/fixture.sh"]}}})
        source = self.root / "tests/fixture.sh"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("fixture", encoding="utf-8")
        profile = queue_tool.coverage.verification_profile(self.root, "old")
        record = {"schema_version": 2, "scope": "pilot-smoke", "profile_id": "old",
                  "profile_revision": profile["profile_revision"], "outcome": "passed",
                  "sha256": "b" * 64, "component": "postgresql", "version": "18.6",
                  "platform": "linux-x86_64", "postgresql_version": "18.6",
                  "test_revision": "a" * 40, "test_cases": ["case-a"],
                  "environment": {"os": "linux", "architecture": "x86_64", "os_version": "2",
                                  "clean_system": True, "endpoint": "current", "image_id": "test-image",
                                  "dependency_check_profile": "test", "dependency_checks_passed": True}}
        self.write("support/verification/record.json", record)
        items = queue_tool.build_queue(self.root)["work_items"]
        core_build = next(i for i in items if i["component"] == "postgresql" and
                          i["postgresql_version"] == "18.6" and i["platform"] == "linux-x86_64" and
                          i["kind"] == "build-core")
        current = next(i for i in items if i["component"] == "postgresql" and
                       i["postgresql_version"] == "18.6" and i["platform"] == "linux-x86_64" and
                       i["kind"] == "verify-core" and i["endpoint"] == "current")
        self.assertEqual(core_build["status"], "needed")
        self.assertEqual(current["status"], "needed")
        self.assertEqual(current["evidence"], "retained-record-unbound-to-inventory")

    def test_work_does_not_reuse_a_download_across_postgresql_minors(self):
        checksum = "a" * 64
        self.write("inventory.json", {
            "postgresql": {"18.6": {"downloads": {"linux-x86_64": {
                "url": "https://example.test/pg.tgz", "sha256": checksum}}}},
            "extensions": {"postgis": {"3.6.4": {"downloads": {"linux-x86_64": [{
                "postgresql_support": {"from": "18.6", "to": "18.6"},
                "url": "https://example.test/postgis.tgz", "sha256": checksum}]}}}},
        })
        items = queue_tool.build_queue(self.root)["work_items"]
        pg16 = next(i for i in items if i["component"] == "postgresql" and i["version"] == "16.15" and i["platform"] == "linux-x86_64" and i["kind"] == "build-core")
        self.assertEqual(pg16["status"], "needed")
        postgis16 = next(i for i in items if i["component"] == "PostGIS" and i["postgresql_major"] == 16 and i["platform"] == "linux-x86_64" and i["kind"] == "build-extension")
        self.assertEqual(postgis16["status"], "needed")

    def test_batch_limit_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            queue_tool.select_batch(queue_tool.build_queue(self.root), 0)

    def test_major_filter_keeps_prerequisites_and_rejects_unknown_selection(self):
        queue = queue_tool.build_queue(self.root)
        batch = queue_tool.select_batch(queue, 100, "PostGIS TIGER Geocoder", "linux-x86_64", 18)
        selected = batch["selected_items"]
        self.assertTrue(selected)
        self.assertTrue(all(item.get("postgresql_major", 18) == 18 for item in selected))
        self.assertTrue(any(item.get("project") == "PostGIS" for item in selected))
        with self.assertRaisesRegex(ValueError, "matches no declared"):
            queue_tool.select_batch(queue, 8, "unknown project")

    def test_exact_item_selection_is_atomic_and_bounded(self):
        queue = queue_tool.build_queue(self.root)
        item_id = queue_tool._id("verify-extension", "PostGIS TIGER Geocoder", "2025.2",
                                 "linux-x86_64", 18, "postgis_tiger_geocoder", "18.6", "current")
        closure = queue_tool.select_item_closure(queue, item_id, 16)
        ids = [item["id"] for item in closure]
        self.assertEqual(ids[-1], item_id)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(set(item["depends_on"]) <= set(ids[:index])
                            for index, item in enumerate(closure)))
        self.assertTrue(any(item.get("project") == "PostGIS" for item in closure))
        with self.assertRaisesRegex(ValueError, "exceeding limit"):
            queue_tool.select_item_closure(queue, item_id, len(closure) - 1)
        with self.assertRaisesRegex(ValueError, "unknown work item"):
            queue_tool.select_item_closure(queue, "missing", 16)

    def test_ambiguous_prerequisite_versions_are_reported_without_selecting_one(self):
        del self.support["extensions"]["PostGIS TIGER Geocoder"]["requires_versions"]
        self.write("support.json", self.support)
        queue = queue_tool.build_queue(self.root)
        tiger_id = queue_tool._id("build-extension", "PostGIS TIGER Geocoder", "2025.2",
                                  "linux-x86_64", 18)
        tiger = next(item for item in queue["work_items"] if item["id"] == tiger_id)
        self.assertFalse(tiger["blocked_by_unresolved_prerequisite"])
        self.assertFalse(any(item["item_id"] == tiger_id for item in queue["unresolved_prerequisites"]))
        batch = queue_tool.select_batch(queue, 100, "PostGIS TIGER Geocoder", "linux-x86_64")
        self.assertIn(tiger_id, [item["id"] for item in batch["selected_items"]])


if __name__ == "__main__":
    unittest.main()
