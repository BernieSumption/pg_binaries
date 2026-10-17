import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "extension_archive_plan", Path(__file__).resolve().parents[1] / "tools" / "extension_archive_plan.py")
extension_archive_plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extension_archive_plan)


class ExtensionArchivePlanTests(unittest.TestCase):
    def setUp(self):
        self.support = {
            "schema_version": 1,
            "version_selection_as_of": "2026-10-17",
            "postgresql": {"minimum_major": 15},
            "os_support": {name: {"minimum_version": "1"} for name in ("macos", "windows", "linux")},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"],
                                       "windows": ["x86_64"], "linux": ["x86_64", "arm64"]},
            "extensions": {
                "RangeProject": {"sql_names": ["range_a", "range_b"], "requires": [], "versions": {
                    "3.0": {"postgresql_minimum_major": 15, "postgresql_maximum_major": 16}}},
                "RestrictedProject": {"sql_names": ["restricted"], "requires": [], "versions": {
                    "15.1": {"postgresql_minimum_major": 15, "postgresql_maximum_major": 15,
                             "operating_systems": ["linux"]}}},
            },
        }
        self.snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01", "supported_majors": [15, 16]}, "releases": [
            {"version": "15.9", "release_date": "2025-09-25"},
            {"version": "15.10", "release_date": "2025-10-01"},
            {"version": "16.6", "release_date": "2025-10-01"},
            {"version": "17.2", "release_date": "2025-10-01"},
        ]}

    def test_compact_group_contains_one_selected_minor_and_its_sql_names(self):
        result = extension_archive_plan.plan(self.support, self.snapshot)
        groups = [item for item in result["candidate_archives"]
                  if item["project"] == "RangeProject" and item["platform"] == "linux-x86_64"]
        by_major = {item["postgresql_major"]: item for item in groups}
        self.assertEqual(set(by_major), {15, 16})
        group = by_major[15]
        self.assertEqual(group["postgresql_version"], "15.10")
        self.assertEqual(group["postgresql_endpoint_versions"], {"from": "15.10", "to": "15.10"})
        self.assertEqual(group["covered_postgresql_versions"], ["15.10"])
        self.assertEqual(group["sql_names"], ["range_a", "range_b"])
        self.assertEqual(group["covered_target_tuple_count"], 2)
        self.assertEqual(by_major[16]["postgresql_endpoint_versions"], {"from": "16.6", "to": "16.6"})
        self.assertEqual(by_major[16]["covered_target_tuple_count"], 2)
        self.assertEqual(group["os_endpoint_labels"], ["minimum", "current"])
        self.assertEqual(group["status"], "candidate-unverified")
        self.assertEqual(group["publication_eligibility"], "not-established")

    def test_declared_platform_and_major_restrictions_survive_planning(self):
        result = extension_archive_plan.plan(self.support, self.snapshot)
        restricted = [item for item in result["candidate_archives"]
                      if item["project"] == "RestrictedProject"]
        self.assertEqual({item["platform"] for item in restricted}, {"linux-x86_64", "linux-arm64"})
        self.assertTrue(all(item["covered_postgresql_versions"] == ["15.10"]
                            for item in restricted))
        self.assertFalse(any("17." in str(item) for item in result["candidate_archives"]))

    def test_current_repository_plan_is_small_and_explicitly_unverified(self):
        root = Path(__file__).resolve().parents[1]
        coverage = extension_archive_plan._coverage
        result = extension_archive_plan.plan(coverage.load_json(root / "support.json"),
                                             coverage.load_json(root / "support/postgresql-releases.json"))
        self.assertEqual(result["status"], "candidate-plan-unverified")
        self.assertTrue(all("candidate" in item["status"] for item in result["candidate_archives"]))
        self.assertTrue(all(item["publication_eligibility"] == "not-established"
                            for item in result["candidate_archives"]))


if __name__ == "__main__":
    unittest.main()
