import importlib.util
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dispatch_plan", ROOT / "tools/dispatch_plan.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class DispatchPlanTests(unittest.TestCase):
    @staticmethod
    def synthetic_queue(status="needed"):
        target = {"project": "Example", "version": "1.0", "platform": "linux-x86_64",
                  "postgresql_version": "18.6", "postgresql_major": 18}
        items = [
            {"id": "z-prerequisite", "kind": "build-core", "status": status, "depends_on": []},
            {"id": "a-target-build", "kind": "build-extension", **target,
             "status": status, "depends_on": ["z-prerequisite"]},
            {"id": "m-target-verify", "kind": "verify-extension", **target,
             "status": status, "depends_on": ["a-target-build"]},
        ]
        return {"work_items": items, "unresolved_prerequisites": []}

    def test_union_uses_topological_order_when_prerequisite_sorts_after_target(self):
        queue = self.synthetic_queue()
        with patch.object(tool.extension_work_queue, "build_queue", return_value=queue):
            result = tool.resolve(ROOT, {"project": "Example", "version": "1.0",
                                         "postgresql_version": "18.6", "platform": "linux-x86_64"})
        self.assertEqual([item["id"] for item in result["work_items"]],
                         ["z-prerequisite", "a-target-build", "m-target-verify"])

    def test_complete_target_is_noop_unless_retry_is_requested(self):
        queue = self.synthetic_queue(status="complete")
        request = {"project": "Example", "version": "1.0", "postgresql_version": "18.6",
                   "platform": "linux-x86_64"}
        with patch.object(tool.extension_work_queue, "build_queue", return_value=queue):
            ordinary = tool.resolve(ROOT, request)
            retry = tool.resolve(ROOT, {**request, "retry": True})
        self.assertFalse(ordinary["should_dispatch"])
        self.assertTrue(retry["should_dispatch"])
        self.assertTrue(all(item["status"] == "complete" for item in retry["work_items"]))

    def fixture_root(self):
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        support = {
            "schema_version": 1, "version_selection_as_of": "2026-10-17",
            "postgresql": {"minimum_major": 15},
            "os_support": {name: {"minimum_version": "1"} for name in ("macos", "windows", "linux")},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"],
                                       "linux": ["x86_64", "arm64"]},
            "extensions": {
                "PostGIS": {"sql_names": ["postgis"], "requires": [], "versions": {
                    "3.6.4": {"postgresql_minimum_major": 15, "postgresql_maximum_major": 18}}},
                "PostGIS TIGER Geocoder": {"sql_names": ["postgis_tiger_geocoder"],
                    "requires": ["PostGIS"], "requires_versions": {"PostGIS": {"minimum_version": "3.6"}},
                    "versions": {"2025.2": {"postgresql_minimum_major": 16, "postgresql_maximum_major": 18}}},
                "HypoPG": {"sql_names": ["hypopg"], "requires": [], "versions": {
                    "1.4.3": {"postgresql_minimum_major": 15}}},
            },
        }
        (root / "support.json").write_text(json.dumps(support))
        policy = root / "policies/extensions.md"
        policy.parent.mkdir()
        policy.write_text("## PostGIS — include\n## PostGIS TIGER Geocoder — include\n## HypoPG — include\n")
        releases = {"as_of": "2026-10-17", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-10-17",
                                       "supported_majors": [15, 16, 17, 18]},
                    "releases": [{"version": version, "release_date": "2026-08-13"}
                                 for version in ("15.19", "16.15", "17.11", "18.6")]}
        snapshot = root / "support/postgresql-releases.json"
        snapshot.parent.mkdir()
        snapshot.write_text(json.dumps(releases))
        (root / "inventory.json").write_text(json.dumps({"postgresql": {}, "extensions": {}}))
        return directory, root

    def test_selects_one_declared_target_and_its_prerequisites(self):
        temp, root = self.fixture_root()
        request = {"project": "PostGIS TIGER Geocoder", "version": "2025.2",
                   "postgresql_version": "18.6", "platform": "linux-x86_64"}
        result = tool.resolve(root, request)
        self.assertEqual(result["target"]["project"], request["project"])
        self.assertFalse(result["retry"])
        self.assertEqual(result["runner"], "ubuntu-24.04")
        kinds = [item["kind"] for item in result["work_items"]]
        self.assertIn("build-core", kinds)
        self.assertIn("build-extension", kinds)
        self.assertIn("verify-extension", kinds)
        self.assertTrue(any(item.get("project") == "PostGIS" for item in result["work_items"]))
        ids = {item["id"] for item in result["work_items"]}
        self.assertTrue(all(set(item.get("depends_on", [])) <= ids for item in result["work_items"]))
        temp.cleanup()

    def test_retry_is_explicit_and_does_not_add_run_or_asset_pins(self):
        temp, root = self.fixture_root()
        request = {"project": "HypoPG", "version": "1.4.3", "postgresql_version": "17.11",
                   "platform": "windows-x86_64", "retry": True}
        result = tool.resolve(root, request)
        self.assertTrue(result["retry"])
        self.assertFalse({"run_id", "asset_id", "asset_url"} & set(result))
        temp.cleanup()

    def test_rejects_undeclared_malformed_and_multi_target_requests(self):
        temp, root = self.fixture_root()
        base = {"project": "HypoPG", "version": "1.4.3", "postgresql_version": "17.11",
                "platform": "linux-x86_64"}
        for update in ({"version": "999"}, {"postgresql_version": "17"},
                       {"platform": "linux-mips"}, {"retry": "yes"}, {"extra_target": {}}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                tool.resolve(root, {**base, **update})
        temp.cleanup()

    def test_hypothetical_new_postgresql_and_extension_selections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture, source = self.fixture_root()
            shutil.copytree(source, root, dirs_exist_ok=True)
            fixture.cleanup()
            support_path = root / "support.json"
            support = json.loads(support_path.read_text())
            support["extensions"]["Example"] = {
                "sql_names": ["example"], "requires": [],
                "versions": {"1.0": {"postgresql_minimum_major": 19}},
            }
            support_path.write_text(json.dumps(support))
            policy = root / "policies/extensions.md"
            policy.write_text(policy.read_text() + "\n## Example — include\n")
            snapshot_path = root / "support/postgresql-releases.json"
            snapshot = json.loads(snapshot_path.read_text())
            snapshot["support_status"]["supported_majors"].append(19)
            release = dict(snapshot["releases"][-1])
            release["version"] = "19.1"
            release["source_archives"] = {}
            snapshot["releases"].append(release)
            support["postgresql"]["minimum_major"] = 15
            snapshot_path.write_text(json.dumps(snapshot))
            result = tool.resolve(root, {"project": "Example", "version": "1.0",
                                         "postgresql_version": "19.1", "platform": "linux-x86_64"})
            self.assertEqual(result["target"]["postgresql_version"], "19.1")
            self.assertEqual(result["target"]["project"], "Example")


if __name__ == "__main__":
    unittest.main()
