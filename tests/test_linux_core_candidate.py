import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import linux_core_candidate as candidate
import source_archive


class LinuxCoreCandidateTests(unittest.TestCase):
    BUILDER_IMAGE_ID = "sha256:" + "b" * 64
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in candidate.CORE_INPUTS:
            source = ROOT / name
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for name in ("support.json", "support/postgresql-releases.json"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "candidate core inputs"], cwd=self.root, check=True)
        self.revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        self.archive_path = self.root / "candidate.tar.gz"
        self.manifest_path = self.root / "discovery.json"
        self.write_candidate()

    def tearDown(self):
        self.temp.cleanup()

    def write_candidate(self, *, producer_revision=None, artifact_name="linux-publication-x86_64-evidence"):
        source = source_archive.source_archive("postgresql", "17.11", "tar.bz2", self.root)
        metadata = {"component": "postgresql", "version": "17.11", "platform": "linux",
                    "architecture": "x86_64", "source_revision": producer_revision or self.revision,
                    "source_archive": source, "builder_image_id": "sha256:" + "b" * 64}
        with tarfile.open(self.archive_path, "w:gz") as archive:
            data = json.dumps(metadata).encode()
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        row = {"component": "postgresql", "version": "17.11", "platform": "linux-x86_64",
               "postgresql_version": "17.11", "path": str(self.archive_path),
               "sha256": hashlib.sha256(self.archive_path.read_bytes()).hexdigest(),
               "source": {"provider": "github-actions", "run_id": "1234", "run_attempt": 2,
                          "head_sha": self.revision, "artifact_name": artifact_name}}
        self.manifest_path.write_text(json.dumps({"schema_version": 1, "archives": [row]}))

    def test_accepts_candidate_with_matching_run_manifest_and_current_recipe(self):
        result = candidate.validate_candidate(
            self.manifest_path, self.archive_path, "17.11", self.BUILDER_IMAGE_ID, self.root)
        self.assertEqual(result["run_id"], "1234")
        self.assertEqual(result["source_revision"], self.revision)

    def test_rejects_candidate_after_relevant_core_recipe_change(self):
        recipe = self.root / "scripts/linux/build-in-container.sh"
        recipe.write_text(recipe.read_text() + "\nchanged\n")
        with self.assertRaisesRegex(ValueError, "build inputs changed"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", self.BUILDER_IMAGE_ID, self.root)

    def test_rejects_run_manifest_source_revision_mismatch(self):
        self.write_candidate(producer_revision="c" * 40)
        with self.assertRaisesRegex(ValueError, "source revision differs"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", self.BUILDER_IMAGE_ID, self.root)

    def test_rejects_candidate_built_with_a_different_docker_image(self):
        with self.assertRaisesRegex(ValueError, "builder image differs"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", "sha256:" + "c" * 64, self.root)

    def test_accepts_selected_workflow_artifact_bound_to_version_and_run(self):
        self.write_candidate(artifact_name="pgvector-linux-selected-17.11-1234")
        result = candidate.validate_candidate(
            self.manifest_path, self.archive_path, "17.11", self.BUILDER_IMAGE_ID, self.root)
        self.assertEqual(result["run_id"], "1234")

    def test_rejects_selected_artifact_with_mismatched_version_or_run(self):
        for name in ("pgvector-linux-selected-18.0-1234", "pgvector-linux-selected-17.11-9876"):
            with self.subTest(name=name):
                self.write_candidate(artifact_name=name)
                with self.assertRaisesRegex(ValueError, "artifact identity"):
                    candidate.validate_candidate(
                        self.manifest_path, self.archive_path, "17.11", self.BUILDER_IMAGE_ID, self.root)


if __name__ == "__main__":
    unittest.main()
