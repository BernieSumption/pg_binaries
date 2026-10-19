import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import hypopg_planner_adapter as adapter


class HypopgPlannerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.pg, self.version, self.platform = "18.6", "1.4.3", "linux-x86_64"
        self.core_name = f"postgresql-{self.pg}-{self.platform}.tar.gz"
        self.extension_name = f"hypopg-{self.version}-postgresql-{self.pg}-{self.platform}.tar.gz"
        self.core_path = self.directory / self.core_name
        self.extension_path = self.directory / self.extension_name
        self.core_path.write_bytes(b"core archive")
        self.extension_path.write_bytes(b"extension archive")
        self.record = {"component": "hypopg", "project": "HypoPG", "version": self.version,
                       "postgresql_version": self.pg, "platform": self.platform,
                       "outcome": "passed", "scope": "publication",
                       "environment": {"endpoint": "current"}, "test_cases": ["probe"],
                       "case_results": {"probe": "passed"}}
        self.identity = {"schema_version": 1, "component": "hypopg",
                         "target": {"project": "hypopg"}, "upstream_sources": {},
                         "dependencies": {}, "build_configuration": {}, "recipes": {},
                         "sha256": "a" * 64}
        self.source = {"run_id": "12345", "run_attempt": 2, "head_sha": "a" * 40,
                       "artifact_name": f"hypopg-linux-selected-{self.pg}-x86_64-12345",
                       "repository": "owner/repo",
                       "artifact_expires_at": "2030-01-01T00:00:00Z"}
        self.manifest = {"target": {"postgresql_version": self.pg, "platform": self.platform},
                         "source": self.source,
                         "files": {self.core_name: str(self.core_path),
                                   self.extension_name: str(self.extension_path),
                                   "core-resolution.json": str(self.directory / "resolution.json"),
                                   "record.json": str(self.directory / "record.json")},
                         "extension_record": "record.json"}
        (self.directory / "resolution.json").write_text("{}")
        (self.directory / "record.json").write_text("{}")
        self.manifest["sha256"] = {"core-resolution.json": hashlib.sha256(
            (self.directory / "resolution.json").read_bytes()).hexdigest()}
        self.validated = {"core": {"component": "postgresql", "version": self.pg,
                                    "postgresql_version": self.pg, "platform": self.platform,
                                    "path": str(self.core_path), "archive_name": self.core_name,
                                    "sha256": hashlib.sha256(self.core_path.read_bytes()).hexdigest()},
                          "extension": {"component": "hypopg", "project": "hypopg",
                                         "version": self.version, "postgresql_version": self.pg,
                                         "platform": self.platform, "path": str(self.extension_path),
                                         "archive_name": self.extension_name,
                                         "sha256": hashlib.sha256(self.extension_path.read_bytes()).hexdigest()},
                          "verification_records": [self.record]}

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, resolution=None):
        resolution = resolution or {"origin": "reused", "provenance": {
            "run_id": self.source["run_id"], "run_attempt": self.source["run_attempt"],
            "head_sha": self.source["head_sha"]}}
        with mock.patch.object(adapter.linux_extension_candidate, "validate_candidate",
                               return_value=self.validated) as extension_check, \
                mock.patch.object(adapter.linux_core_resolution, "validate_resolution",
                                   return_value=resolution), \
                mock.patch.object(adapter.linux_core_candidate, "validate_candidate",
                                   return_value={"source_revision": "b" * 40}), \
                mock.patch.object(adapter.linux_extension_candidate, "_metadata",
                                   return_value={"builder_inputs": {"base_image": "ubuntu:22.04"}}), \
                mock.patch.object(adapter.hypopg_build_inputs, "selected_identity",
                                   return_value=self.identity):
            result = adapter.checked_candidate_inputs(
                self.manifest, ROOT, core_base_image_digest="sha256:" + "b" * 64,
                core_builder_packages_sha256="c" * 64,
                hypopg_builder_packages_sha256="d" * 64)
        return result, extension_check

    def test_returns_checked_overlay_with_only_exact_extension_record(self):
        result, extension_check = self.invoke()
        extension_check.assert_called_once()
        overlay = result["planner_overlay"]
        self.assertEqual([item["component"] for item in overlay["candidate_archives"]],
                         ["postgresql", "hypopg"])
        self.assertEqual(len(overlay["verification_records"]), 1)
        self.assertEqual(overlay["verification_records"][0]["component"], "hypopg")
        self.assertEqual(overlay["verification_records"][0]["_record_file"], "record.json")
        self.assertTrue(overlay["verification_records"][0]["_profile_current"])
        self.assertNotIn("postgresql", [r["component"] for r in overlay["verification_records"]])

    def test_rejects_stale_core_recipe(self):
        with mock.patch.object(adapter.linux_extension_candidate, "validate_candidate",
                               return_value=self.validated), \
                mock.patch.object(adapter.linux_core_resolution, "validate_resolution",
                                   return_value={"origin": "reused", "provenance": {
                                       "run_id": self.source["run_id"],
                                       "run_attempt": self.source["run_attempt"],
                                       "head_sha": self.source["head_sha"]}}), \
                mock.patch.object(adapter.linux_core_candidate, "validate_candidate",
                                   side_effect=ValueError("core build inputs changed")):
            with self.assertRaisesRegex(adapter.PlannerAdapterError, "core candidate rejected"):
                adapter.checked_candidate_inputs(
                    self.manifest, ROOT, core_base_image_digest="sha256:" + "b" * 64,
                    core_builder_packages_sha256="c" * 64,
                    hypopg_builder_packages_sha256="d" * 64)

    def test_accepts_core_built_in_same_run(self):
        resolution = {"origin": "built", "provenance": {
            "run_id": self.source["run_id"], "run_attempt": self.source["run_attempt"],
            "run_sha": self.source["head_sha"], "repository": self.source["repository"]}}
        result, _ = self.invoke(resolution)
        self.assertEqual(result["planner_overlay"]["candidate_archives"][0]["component"],
                         "postgresql")

    def test_rejects_built_core_from_other_run(self):
        resolution = {"origin": "built", "provenance": {
            "run_id": "99999", "run_attempt": self.source["run_attempt"],
            "run_sha": self.source["head_sha"], "repository": self.source["repository"]}}
        with self.assertRaisesRegex(adapter.PlannerAdapterError, "candidate producer"):
            self.invoke(resolution)

    def test_rejects_modified_core_resolution_record(self):
        (self.directory / "resolution.json").write_text('{"altered":true}')
        with self.assertRaisesRegex(adapter.PlannerAdapterError, "candidate manifest SHA-256"):
            self.invoke()

    def test_rejects_stale_extension_build_inputs(self):
        with mock.patch.object(adapter.linux_extension_candidate, "validate_candidate",
                               side_effect=ValueError("extension build inputs differ")):
            with self.assertRaisesRegex(adapter.PlannerAdapterError, "HypoPG candidate rejected"):
                adapter.checked_candidate_inputs(
                    self.manifest, ROOT, core_base_image_digest="sha256:" + "b" * 64,
                    core_builder_packages_sha256="c" * 64,
                    hypopg_builder_packages_sha256="d" * 64)

    def test_rejects_failed_core_resolution_provenance(self):
        with mock.patch.object(adapter.linux_extension_candidate, "validate_candidate",
                               return_value=self.validated), \
                mock.patch.object(adapter.linux_core_resolution, "validate_resolution",
                                   side_effect=ValueError("resolution digest mismatch")):
            with self.assertRaisesRegex(adapter.PlannerAdapterError, "core resolution provenance rejected"):
                adapter.checked_candidate_inputs(
                    self.manifest, ROOT, core_base_image_digest="sha256:" + "b" * 64,
                    core_builder_packages_sha256="c" * 64,
                    hypopg_builder_packages_sha256="d" * 64)


if __name__ == "__main__":
    unittest.main()
