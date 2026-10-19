import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_input_identity
import pgvector_planner_adapter as adapter


class PgvectorPlannerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.pg, self.version, self.platform = "17.11", "0.8.7", "linux-x86_64"
        self.core_name = f"postgresql-{self.pg}-{self.platform}.tar.gz"
        self.vector_name = f"pgvector-{self.version}-postgresql-{self.pg}-{self.platform}.tar.gz"
        self.core_path = self.directory / self.core_name
        self.vector_path = self.directory / self.vector_name
        self.core_path.write_bytes(b"core")
        payload = {"build_inputs": {"schema_version": 1}}
        data = json.dumps(payload).encode()
        with tarfile.open(self.vector_path, "w:gz") as archive:
            info = tarfile.TarInfo("metadata.json")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        self.source = {"run_id": "123", "run_attempt": 1, "head_sha": "a" * 40,
                       "artifact_name": f"pgvector-linux-selected-{self.pg}-123",
                       "artifact_expires_at": "2030-01-01T00:00:00Z"}
        self.manifest = {"target": {"postgresql_version": self.pg,
                                    "pgvector_version": self.version,
                                    "platform": self.platform},
                         "source": self.source,
                         "files": {self.core_name: str(self.core_path),
                                   self.vector_name: str(self.vector_path)}}
        self.core_record = {"component": "postgresql", "version": self.pg}
        self.extension_record = {"component": "vector", "version": self.version}
        self.identity = {"schema_version": 1, "component": "pgvector", "target": {"project": "pgvector"},
                         "upstream_sources": {}, "dependencies": {}, "build_configuration": {},
                         "recipes": {}, "sha256": "0" * 64}

    def tearDown(self):
        self.temp.cleanup()

    @mock.patch.object(adapter, "pgvector_build_inputs")
    @mock.patch.object(adapter, "linux_core_candidate")
    @mock.patch.object(adapter, "pgvector_candidate_records")
    def test_returns_checked_core_extension_and_records(self, records, core, inputs):
        records.validate_candidate_records.return_value = {
            "core": self.core_record, "extension": self.extension_record}
        inputs.selected_identity.return_value = self.identity
        with mock.patch.object(adapter, "_metadata", side_effect=[{"build_inputs": {}},
                                                                    {"builder_inputs": {}}]), \
                mock.patch.object(adapter.build_input_identity, "assess_reuse",
                               return_value={"reusable": True, "reason": "matches"}):
            result = adapter.checked_candidate_inputs(
                self.manifest, ROOT, core_base_image_digest="sha256:" + "b" * 64,
                core_builder_packages_sha256="c" * 64,
                pgvector_builder_packages_sha256="d" * 64)
        core.validate_candidate.assert_called_once()
        overlay = result["planner_overlay"]
        self.assertEqual([row["component"] for row in overlay["candidate_archives"]],
                         ["postgresql", "pgvector"])
        self.assertEqual(overlay["candidate_archives"][1]["build_input_identity"], self.identity)
        self.assertEqual(overlay["candidate_archives"][0]["sha256"], hashlib.sha256(b"core").hexdigest())
        self.assertEqual(len(overlay["verification_records"]), 2)
        self.assertEqual([row["component"] for row in result["planner_overlay"]["candidate_archives"]],
                         ["postgresql", "pgvector"])
        self.assertEqual(result["planner_overlay"]["candidate_archives"][0]["validation"],
                         "linux-core-candidate-and-current-inputs")
        self.assertEqual(len(result["planner_overlay"]["verification_records"]), 2)
        self.assertTrue(all(row["_profile_current"] for row in
                            result["planner_overlay"]["verification_records"]))

    @mock.patch.object(adapter, "pgvector_build_inputs")
    @mock.patch.object(adapter, "linux_core_candidate")
    @mock.patch.object(adapter, "pgvector_candidate_records")
    def test_rejects_pgvector_dependency_identity_mismatch(self, records, core, inputs):
        records.validate_candidate_records.return_value = {
            "core": self.core_record, "extension": self.extension_record}
        inputs.selected_identity.return_value = self.identity
        with mock.patch.object(adapter, "_metadata", return_value={"build_inputs": {}}), \
                mock.patch.object(adapter.build_input_identity, "assess_reuse",
                               return_value={"reusable": False, "reason": "build input identity mismatch"}):
            with self.assertRaisesRegex(adapter.PlannerAdapterError, "pgvector candidate build inputs differ"):
                adapter.checked_candidate_inputs(
                    self.manifest, ROOT, core_base_image_digest="sha256:" + "b" * 64,
                    core_builder_packages_sha256="c" * 64,
                    pgvector_builder_packages_sha256="d" * 64)


if __name__ == "__main__":
    unittest.main()
