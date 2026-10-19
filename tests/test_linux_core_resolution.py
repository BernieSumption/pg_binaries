import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from tools import linux_core_resolution as resolution


class LinuxCoreResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.archive = Path(self.temporary.name) / "postgresql-17.11-linux-x86_64.tar.gz"
        self.manifest = {
            "component": "postgresql", "version": "17.11", "platform": "linux",
            "architecture": "x86_64", "source_revision": "a" * 40, "build_id": "github-12-1",
            "builder_inputs": {"base_image": "ubuntu:22.04", "base_image_digest": "sha256:" + "b" * 64,
                               "packages_sha256": "c" * 64},
        }
        with tarfile.open(self.archive, "w:gz") as tar:
            payload = json.dumps(self.manifest).encode()
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))

    def test_built_record_uses_archive_and_current_run_provenance(self):
        env = {"GITHUB_RUN_ID": "99", "GITHUB_RUN_ATTEMPT": "2",
               "GITHUB_REPOSITORY": "owner/repo", "GITHUB_WORKFLOW_REF": "owner/repo/.github/workflows/build.yml@refs/heads/spike",
               "GITHUB_SHA": "d" * 40}
        record = resolution.create_record(self.archive, "17.11", "x86_64", "built", environ=env)
        self.assertEqual(record["origin"], "built")
        self.assertEqual(record["archive"], self.archive.name)
        self.assertEqual(record["sha256"], hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertEqual(record["provenance"]["run_id"], "99")
        record_path = Path(self.temporary.name) / "core-resolution.json"
        record_path.write_text(json.dumps(record))
        self.assertEqual(resolution.validate_resolution(record_path, self.archive, "17.11", "x86_64"), record)
        record["sha256"] = "e" * 64
        record_path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "digest"):
            resolution.validate_resolution(record_path, self.archive, "17.11", "x86_64")

    def test_reused_record_requires_and_binds_validated_candidate_identity(self):
        candidate = {"run_id": "12", "run_attempt": 1, "artifact_revision": "d" * 40,
                     "artifact_name": "linux-publication-x86_64-evidence",
                     "sha256": hashlib.sha256(self.archive.read_bytes()).hexdigest()}
        record = resolution.create_record(self.archive, "17.11", "x86_64", "reused", candidate)
        self.assertEqual(record["provenance"]["head_sha"], "d" * 40)
        with self.assertRaisesRegex(ValueError, "requires validated"):
            resolution.create_record(self.archive, "17.11", "x86_64", "reused")

    def test_stale_candidate_cannot_change_fallback_origin(self):
        stale_candidate = {"run_id": "12", "run_attempt": 1, "sha256": "e" * 64}
        record = resolution.create_record(
            self.archive, "17.11", "x86_64", "built", stale_candidate,
            {"GITHUB_RUN_ID": "99", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_REPOSITORY": "owner/repo",
             "GITHUB_WORKFLOW_REF": "owner/repo/.github/workflows/build.yml@refs/heads/spike",
             "GITHUB_SHA": "d" * 40})
        self.assertEqual(record["origin"], "built")
        self.assertEqual(record["provenance"]["run_id"], "99")

    def test_rejects_wrong_archive_target_and_invalid_run_strings(self):
        with self.assertRaisesRegex(ValueError, "target"):
            resolution.create_record(self.archive, "18.0", "x86_64", "built", environ={})
        with self.assertRaisesRegex(ValueError, "current run ID"):
            resolution.create_record(self.archive, "17.11", "x86_64", "built", environ={"GITHUB_RUN_ID": "bad"})


if __name__ == "__main__":
    unittest.main()
