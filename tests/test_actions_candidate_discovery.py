import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile


SPEC = importlib.util.spec_from_file_location(
    "actions_candidate_discovery", Path(__file__).resolve().parents[1] / "tools" / "actions_candidate_discovery.py")
discovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(discovery)


class ActionsCandidateDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive_name = "example-1.0-postgresql-15.10-linux-x86_64.tar.gz"
        self.archive = b"archive bytes"
        self.sidecar = f"{hashlib.sha256(self.archive).hexdigest()}  {self.archive_name}\n".encode()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr(self.archive_name, self.archive)
            z.writestr(self.archive_name + ".sha256", self.sidecar)
        self.zip_bytes = buffer.getvalue()
        self.repo = "example/project"
        self.run = {"id": 123, "run_number": 8, "repository": {"full_name": self.repo},
                    "head_repository": {"full_name": self.repo},
                    "head_sha": "a" * 40,
                    "path": ".github/workflows/build.yml", "head_branch": "spike", "event": "push",
                    "status": "completed", "conclusion": "success"}
        self.artifact = {"id": 456, "name": "candidate-123", "expired": False,
                         "expires_at": "2099-01-01T00:00:00Z",
                         "digest": "sha256:" + hashlib.sha256(self.zip_bytes).hexdigest()}
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def fake_run(self, args, **kwargs):
        self.calls.append(args)
        endpoint = args[2]
        if "/actions/artifacts?name=" in endpoint:
            value = {"artifacts": [dict(self.artifact, workflow_run={
                "id": self.run["id"], "head_sha": self.run["head_sha"]})]}
            output = json.dumps(value).encode()
        elif endpoint.endswith(f"/actions/runs/{self.run['id']}"):
            output = json.dumps(self.run).encode()
        elif "/workflows/" in endpoint:
            value = {"workflow_runs": [self.run]}
            output = json.dumps(value).encode()
        elif "/runs/" in endpoint:
            output = json.dumps({"artifacts": [self.artifact]}).encode()
        else:
            output = self.zip_bytes
        if "stdout" in kwargs:
            kwargs["stdout"].write(output)
            return subprocess.CompletedProcess(args, 0, None, b"")
        return subprocess.CompletedProcess(args, 0, output, b"")

    def invoke(self):
        return discovery.discover(repository=self.repo, workflow="build.yml", branch="spike",
            current_run_id="999", artifact_name_template="candidate-{run_id}",
            archive_basename=self.archive_name, project="Example", version="1.0",
            platform="linux-x86_64", postgresql_version="15.10",
            output_directory=self.root / "out", manifest_path=self.root / "manifest.json")

    def test_discovers_extracts_and_writes_manifest(self):
        with patch.object(discovery.subprocess, "run", side_effect=self.fake_run):
            self.assertEqual(self.invoke(), [])
        data = json.loads((self.root / "manifest.json").read_text())
        row = data["archives"][0]
        self.assertEqual(row["source"]["run_id"], "123")
        self.assertEqual(row["source"]["head_sha"], "a" * 40)
        self.assertEqual(row["source"]["artifact_name"], "candidate-123")
        self.assertEqual(row["sha256"], hashlib.sha256(self.archive).hexdigest())
        self.assertEqual(Path(row["path"]).read_bytes(), self.archive)
        self.assertEqual(len(self.calls), 3)

    def test_fixed_artifact_name_is_accepted(self):
        self.artifact["name"] = "linux-core"
        with patch.object(discovery.subprocess, "run", side_effect=self.fake_run):
            reasons = discovery.discover(repository=self.repo, workflow="build.yml", branch="spike",
                current_run_id="999", artifact_name_template="linux-core",
                archive_basename=self.archive_name, project="PostgreSQL", version="15.10",
                platform="linux-x86_64", postgresql_version="15.10",
                output_directory=self.root / "out", manifest_path=self.root / "manifest.json")
        self.assertEqual(reasons, [])
        row = json.loads((self.root / "manifest.json").read_text())["archives"][0]
        self.assertEqual(row["source"]["artifact_name"], "linux-core")
        self.assertEqual(len(self.calls), 3)

    def test_fixed_artifact_name_rejects_unrelated_workflow(self):
        self.artifact["name"] = "linux-core"
        self.run["path"] = ".github/workflows/other.yml"
        with patch.object(discovery.subprocess, "run", side_effect=self.fake_run):
            reasons = discovery.discover(repository=self.repo, workflow="build.yml", branch="spike",
                current_run_id="999", artifact_name_template="linux-core",
                archive_basename=self.archive_name, project="PostgreSQL", version="15.10",
                platform="linux-x86_64", postgresql_version="15.10",
                output_directory=self.root / "out", manifest_path=self.root / "manifest.json")
        self.assertTrue(any("source run identity" in reason for reason in reasons))
        self.assertEqual(json.loads((self.root / "manifest.json").read_text())["archives"], [])

    def test_nested_archive_pair_is_extracted_flattened(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("pilot/" + self.archive_name, self.archive)
            z.writestr("pilot/" + self.archive_name + ".sha256", self.sidecar)
        self.zip_bytes = buffer.getvalue()
        self.artifact["digest"] = "sha256:" + hashlib.sha256(self.zip_bytes).hexdigest()
        with patch.object(discovery.subprocess, "run", side_effect=self.fake_run):
            self.assertEqual(self.invoke(), [])
        self.assertEqual((self.root / "out" / self.archive_name).read_bytes(), self.archive)

    def test_ambiguous_archive_pairs_are_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            for prefix in ("pilot", "other"):
                z.writestr(prefix + "/" + self.archive_name, self.archive)
                z.writestr(prefix + "/" + self.archive_name + ".sha256", self.sidecar)
        self.zip_bytes = buffer.getvalue()
        self.artifact["digest"] = "sha256:" + hashlib.sha256(self.zip_bytes).hexdigest()
        with patch.object(discovery.subprocess, "run", side_effect=self.fake_run):
            reasons = self.invoke()
        self.assertTrue(any("ambiguous" in reason for reason in reasons))
        self.assertEqual(json.loads((self.root / "manifest.json").read_text())["archives"], [])

    def test_rejects_wrong_run_identity_and_current_run(self):
        for field, value in (("head_branch", "main"), ("head_sha", "invalid"),
                             ("event", "workflow_dispatch"),
                             ("conclusion", "failure"), ("id", 999)):
            with self.subTest(field=field):
                self.run[field] = value
                with patch.object(discovery.subprocess, "run", side_effect=self.fake_run):
                    self.invoke()
                self.assertEqual(json.loads((self.root / "manifest.json").read_text())["archives"], [])
                self.run[field] = {"head_branch": "spike", "head_sha": "a" * 40,
                                   "event": "push", "conclusion": "success", "id": 123}[field]

    def test_digest_mismatch_is_rejected(self):
        self.artifact["digest"] = "sha256:" + "0" * 64
        with patch.object(discovery.subprocess, "run", side_effect=self.fake_run):
            reasons = self.invoke()
        self.assertTrue(any("digest differs" in reason for reason in reasons))
        self.assertEqual(json.loads((self.root / "manifest.json").read_text())["archives"], [])

    def test_expired_artifact_is_rejected(self):
        self.artifact["expires_at"] = "2000-01-01T00:00:00Z"
        with patch.object(discovery.subprocess, "run", side_effect=self.fake_run):
            reasons = self.invoke()
        self.assertTrue(any("expired" in reason for reason in reasons))

    def test_expired_latest_artifact_uses_older_successful_run(self):
        latest = dict(self.run, id=124, run_number=9)
        expired = dict(self.artifact, id=457, name="candidate-124",
                       expires_at="2000-01-01T00:00:00Z")

        def fake_run(args, **kwargs):
            endpoint = args[2]
            if "/workflows/" in endpoint:
                payload = {"workflow_runs": [latest, self.run]}
            elif "/runs/124/" in endpoint:
                payload = {"artifacts": [expired]}
            elif "/runs/123/" in endpoint:
                payload = {"artifacts": [self.artifact]}
            else:
                kwargs["stdout"].write(self.zip_bytes)
                return subprocess.CompletedProcess(args, 0, None, b"")
            return subprocess.CompletedProcess(args, 0, json.dumps(payload).encode(), b"")

        with patch.object(discovery.subprocess, "run", side_effect=fake_run):
            reasons = self.invoke()
        row = json.loads((self.root / "manifest.json").read_text())["archives"][0]
        self.assertEqual(row["source"]["run_id"], "123")
        self.assertEqual(reasons, [])

    def test_missing_artifact_and_absent_candidate_write_empty_manifest(self):
        self.artifact["name"] = "other"
        with patch.object(discovery.subprocess, "run", side_effect=self.fake_run):
            reasons = self.invoke()
        self.assertTrue(any("absent" in reason for reason in reasons))
        self.assertEqual(json.loads((self.root / "manifest.json").read_text())["archives"], [])

    def test_tampered_sidecar_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr(self.archive_name, self.archive)
            z.writestr(self.archive_name + ".sha256", ("0" * 64 + "  " + self.archive_name).encode())
        self.zip_bytes = buffer.getvalue()
        self.artifact["digest"] = "sha256:" + hashlib.sha256(self.zip_bytes).hexdigest()
        with patch.object(discovery.subprocess, "run", side_effect=self.fake_run):
            reasons = self.invoke()
        self.assertTrue(any("sidecar checksum" in reason for reason in reasons))

    def test_cli_accepts_all_hyphenated_options(self):
        args = [
            "--repository", self.repo, "--workflow", "build.yml", "--branch", "spike",
            "--current-run-id", "999", "--artifact-name-template", "candidate-{run_id}",
            "--archive-basename", self.archive_name, "--project", "Example", "--version", "1.0",
            "--platform", "linux-x86_64", "--postgresql-version", "15.10",
            "--output-directory", str(self.root / "out"), "--manifest-path", str(self.root / "manifest.json"),
        ]
        with patch.object(discovery, "discover", return_value=[]):
            self.assertEqual(discovery.main(args), 0)

    def test_top_level_api_failure_fails_cli(self):
        args = [
            "--repository", self.repo, "--workflow", "build.yml", "--branch", "spike",
            "--current-run-id", "999", "--artifact-name-template", "candidate-{run_id}",
            "--archive-basename", self.archive_name, "--project", "Example", "--version", "1.0",
            "--platform", "linux-x86_64", "--postgresql-version", "15.10",
            "--output-directory", str(self.root / "out"), "--manifest-path", str(self.root / "manifest.json"),
        ]
        failed = subprocess.CompletedProcess([], 1, b"", b"API rate limit exceeded")
        with patch.object(discovery.subprocess, "run", return_value=failed):
            with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(discovery.main(args), 1)
                self.assertIn("rate limit", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
