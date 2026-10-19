import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import hypopg_linux_candidate as candidate


class HypoPGLinuxCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.repository, self.branch, self.current_run = "owner/repo", "spike", "999"
        self.pg, self.arch = "17.11", "x86_64"
        self.run_id, self.artifact_id = "42", "77"
        self.core = f"postgresql-{self.pg}-linux-{self.arch}.tar.gz"
        self.extension = f"hypopg-1.4.3-postgresql-{self.pg}-linux-{self.arch}.tar.gz"
        self.record = f"hypopg-1.4.3-postgresql-{self.pg}-linux-{self.arch}-current-{self.run_id}.json"
        self.artifact_name = f"hypopg-linux-selected-{self.pg}-{self.arch}-{self.run_id}"
        files = {
            f"bundle/core/pilot/{self.core}": b"core archive",
            f"bundle/core/pilot/{self.core}.sha256": b"core sidecar",
            f"bundle/hypopg/{self.extension}": b"extension archive",
            f"bundle/hypopg/{self.extension}.sha256": b"extension sidecar",
            "bundle/core/pilot/core-resolution.json": b'{"schema_version":1}',
            f"bundle/hypopg-publication/records/{self.record}": b'{"record":"publication"}',
            f"bundle/support/verification/{self.record}": b'{"record":"duplicate"}',
        }
        files[f"bundle/core/pilot/{self.core}.sha256"] = (
            hashlib.sha256(files[f"bundle/core/pilot/{self.core}"]).hexdigest()
            + "  " + self.core + "\n").encode()
        files[f"bundle/hypopg/{self.extension}.sha256"] = (
            hashlib.sha256(files[f"bundle/hypopg/{self.extension}"]).hexdigest()
            + "  " + self.extension + "\n").encode()
        self.zip_path = self.directory / "artifact.zip"
        with zipfile.ZipFile(self.zip_path, "w") as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        self.zip_digest = hashlib.sha256(self.zip_path.read_bytes()).hexdigest()
        self.run = {"id": self.run_id, "run_number": 1, "run_attempt": 1,
                    "path": ".github/workflows/linux-changed-profiles.yml",
                    "repository": {"full_name": self.repository},
                    "head_repository": {"full_name": self.repository},
                    "head_sha": "a" * 40, "head_branch": self.branch,
                    "event": "workflow_dispatch", "status": "completed",
                    "conclusion": "success"}
        self.artifact = {"id": self.artifact_id, "name": self.artifact_name,
                         "expired": False, "expires_at": "2099-01-01T00:00:00Z",
                         "digest": "sha256:" + self.zip_digest,
                         "workflow_run": {"id": self.run_id, "head_sha": "a" * 40}}

    def tearDown(self):
        self.temp.cleanup()

    def _gh(self, args):
        return ({"workflow_runs": [self.run]} if "/workflows/" in args[0]
                else {"artifacts": [self.artifact]})

    def retrieve(self):
        output = self.directory / "out"
        manifest_path = output / "candidate.json"
        def download(repository, artifact_id, claim, temporary):
            self.assertEqual(repository, self.repository)
            self.assertEqual(artifact_id, self.artifact_id)
            self.assertEqual(claim, "sha256:" + self.zip_digest)
            return self.zip_path
        with mock.patch.object(candidate.discovery, "_gh", side_effect=self._gh), \
                mock.patch.object(candidate.bundle, "_download_verified_zip",
                                  side_effect=download):
            manifest = candidate.retrieve(
                repository=self.repository, branch=self.branch,
                current_run_id=self.current_run, postgresql_version=self.pg,
                architecture=self.arch, output_directory=output,
                manifest_path=manifest_path)
        return manifest, manifest_path

    def test_retrieves_exact_artifact_and_emits_semantic_manifest(self):
        manifest, manifest_path = self.retrieve()
        self.assertEqual(json.loads(manifest_path.read_text()), manifest)
        self.assertEqual(manifest["target"], {"postgresql_version": self.pg,
                                              "platform": "linux-x86_64"})
        self.assertEqual(manifest["source"]["run_id"], self.run_id)
        self.assertEqual(manifest["source"]["artifact_name"], self.artifact_name)
        self.assertEqual(manifest["extension_record"], self.record)
        self.assertIn("core-resolution.json", manifest["files"])
        self.assertEqual(Path(manifest["files"][self.record]).read_bytes(),
                         b'{"record":"publication"}')
        self.assertEqual(manifest["sha256"][self.core],
                         hashlib.sha256(Path(manifest["files"][self.core]).read_bytes()).hexdigest())

    def test_rejects_expired_artifact(self):
        self.artifact["expires_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaisesRegex(candidate.CandidateRetrievalError, "expiry"):
            self.retrieve()

    def test_rejects_artifact_claiming_a_different_run(self):
        self.artifact["workflow_run"]["id"] = "41"
        with mock.patch.object(candidate.discovery, "_gh", side_effect=self._gh):
            with self.assertRaisesRegex(candidate.CandidateRetrievalError,
                                        "no matching successful producer"):
                candidate.retrieve(repository=self.repository, branch=self.branch,
                                   current_run_id=self.current_run,
                                   postgresql_version=self.pg, architecture=self.arch,
                                   output_directory=self.directory / "out",
                                   manifest_path=self.directory / "out/candidate.json")

    def test_rejects_unconfigured_extension_version(self):
        with self.assertRaisesRegex(candidate.CandidateRetrievalError, "supports only 1.4.3"):
            candidate.retrieve(repository=self.repository, branch=self.branch,
                               current_run_id=self.current_run,
                               postgresql_version=self.pg, extension_version="1.4.4",
                               architecture=self.arch, output_directory=self.directory / "out",
                               manifest_path=self.directory / "out/candidate.json")


if __name__ == "__main__":
    unittest.main()
