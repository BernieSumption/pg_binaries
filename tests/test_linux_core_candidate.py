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
    BASE_IMAGE_DIGEST = "sha256:" + "c" * 64
    BUILDER_PACKAGES_SHA256 = "d" * 64
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in candidate.CORE_INPUTS:
            source = ROOT / name
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        workflow = ROOT / candidate.LEGACY_CORE_WORKFLOW
        workflow_target = self.root / candidate.LEGACY_CORE_WORKFLOW
        workflow_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workflow, workflow_target)
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

    def write_candidate(self, *, producer_revision=None, run_revision=None,
                        artifact_name="linux-publication-x86_64-evidence",
                        builder_image_id=BUILDER_IMAGE_ID, architecture="x86_64"):
        source = source_archive.source_archive("postgresql", "17.11", "tar.bz2", self.root)
        metadata = {"component": "postgresql", "version": "17.11", "platform": "linux",
                    "architecture": architecture, "source_revision": producer_revision or self.revision,
                    "source_archive": source, "builder_image_id": builder_image_id,
                    "builder_inputs": {"base_image": "ubuntu:22.04",
                                       "base_image_digest": self.BASE_IMAGE_DIGEST,
                                       "packages_sha256": self.BUILDER_PACKAGES_SHA256}}
        with tarfile.open(self.archive_path, "w:gz") as archive:
            data = json.dumps(metadata).encode()
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        row = {"component": "postgresql", "version": "17.11", "platform": f"linux-{architecture}",
               "postgresql_version": "17.11", "path": str(self.archive_path),
               "sha256": hashlib.sha256(self.archive_path.read_bytes()).hexdigest(),
               "source": {"provider": "github-actions", "run_id": "1234", "run_attempt": 2,
                          "head_sha": run_revision or self.revision, "artifact_name": artifact_name}}
        self.manifest_path.write_text(json.dumps({"schema_version": 1, "archives": [row]}))

    def test_accepts_candidate_with_matching_run_manifest_and_current_recipe(self):
        result = candidate.validate_candidate(
            self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
            self.BUILDER_PACKAGES_SHA256, self.root)
        self.assertEqual(result["run_id"], "1234")
        self.assertEqual(result["source_revision"], self.revision)

    def test_rejects_candidate_after_relevant_core_recipe_change(self):
        recipe = self.root / "scripts/linux/build-in-container.sh"
        recipe.write_text(recipe.read_text() + "\nchanged\n")
        with self.assertRaisesRegex(ValueError, "build inputs changed"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
                self.BUILDER_PACKAGES_SHA256, self.root)

    def test_accepts_candidate_after_unrelated_extension_workflow_change(self):
        workflow = self.root / candidate.LEGACY_CORE_WORKFLOW
        workflow.write_text(workflow.read_text().replace(
            "Build PostGIS 3.6.4 against the publication PostgreSQL archive",
            "Build PostGIS 3.6.4 with an updated extension workflow label"))
        result = candidate.validate_candidate(
            self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
            self.BUILDER_PACKAGES_SHA256, self.root)
        self.assertEqual(result["run_id"], "1234")

    def test_rejects_candidate_after_legacy_core_build_invocation_change(self):
        workflow = self.root / candidate.LEGACY_CORE_WORKFLOW
        workflow.write_text(workflow.read_text().replace(
            'run: scripts/linux/build.sh "$RUNNER_TEMP/pilot"',
            'run: scripts/linux/build.sh "$RUNNER_TEMP/pilot" --core-only'))
        with self.assertRaisesRegex(ValueError, "build inputs changed"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
                self.BUILDER_PACKAGES_SHA256, self.root)

    def test_rejects_candidate_after_legacy_core_runner_setup_change(self):
        workflow = self.root / candidate.LEGACY_CORE_WORKFLOW
        workflow.write_text(workflow.read_text().replace(
            "runner: ubuntu-24.04\n", "runner: ubuntu-22.04\n", 1))
        with self.assertRaisesRegex(ValueError, "build inputs changed"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
                self.BUILDER_PACKAGES_SHA256, self.root)

    def test_fails_closed_when_legacy_core_workflow_is_missing(self):
        (self.root / candidate.LEGACY_CORE_WORKFLOW).unlink()
        with self.assertRaisesRegex(ValueError, "legacy Linux core workflow is unavailable"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
                self.BUILDER_PACKAGES_SHA256, self.root)

    def test_rejects_unknown_core_build_revision(self):
        self.write_candidate(producer_revision="c" * 40)
        with self.assertRaisesRegex(ValueError, "source revision is unavailable"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
                self.BUILDER_PACKAGES_SHA256, self.root)

    def test_accepts_archive_republished_by_later_run_with_unchanged_core_inputs(self):
        (self.root / "readme.txt").write_text("new workflow packaging\n")
        subprocess.run(["git", "add", "readme.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "repackage unchanged core"], cwd=self.root, check=True)
        later_run = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        self.write_candidate(run_revision=later_run)
        result = candidate.validate_candidate(
            self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
            self.BUILDER_PACKAGES_SHA256, self.root)
        self.assertEqual(result["source_revision"], self.revision)
        self.assertEqual(result["artifact_revision"], later_run)

    def test_accepts_same_builder_inputs_with_a_different_docker_image_id(self):
        self.write_candidate(builder_image_id="sha256:" + "e" * 64)
        result = candidate.validate_candidate(
            self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
            self.BUILDER_PACKAGES_SHA256, self.root)
        self.assertEqual(result["run_id"], "1234")

    def test_rejects_candidate_with_different_base_or_package_inputs(self):
        for base, packages in (("sha256:" + "e" * 64, self.BUILDER_PACKAGES_SHA256),
                               (self.BASE_IMAGE_DIGEST, "f" * 64)):
            with self.subTest(base=base, packages=packages):
                with self.assertRaisesRegex(ValueError, "builder inputs differ"):
                    candidate.validate_candidate(
                        self.manifest_path, self.archive_path, "17.11", base, packages,
                        self.root)

    def test_rejects_legacy_manifest_without_builder_input_identity(self):
        with tarfile.open(self.archive_path, "r:gz") as archive:
            metadata = json.load(archive.extractfile("postgresql/manifest.json"))
        del metadata["builder_inputs"]
        with tarfile.open(self.archive_path, "w:gz") as archive:
            data = json.dumps(metadata).encode()
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        row = json.loads(self.manifest_path.read_text())
        row["archives"][0]["sha256"] = hashlib.sha256(self.archive_path.read_bytes()).hexdigest()
        self.manifest_path.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "lacks checked builder input identity"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
                self.BUILDER_PACKAGES_SHA256, self.root)

    def test_accepts_selected_workflow_artifact_bound_to_version_and_run(self):
        self.write_candidate(artifact_name="pgvector-linux-selected-17.11-1234")
        result = candidate.validate_candidate(
            self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
            self.BUILDER_PACKAGES_SHA256, self.root)
        self.assertEqual(result["run_id"], "1234")

    def test_selected_artifact_template_is_bound_to_run_and_version(self):
        self.write_candidate(artifact_name="hypopg-linux-selected-17.11-1234")
        result = candidate.validate_candidate(
            self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
            self.BUILDER_PACKAGES_SHA256, self.root, "x86_64",
            "hypopg-linux-selected-17.11-{run_id}")
        self.assertEqual(result["run_id"], "1234")
        with self.assertRaisesRegex(ValueError, "artifact identity"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
                self.BUILDER_PACKAGES_SHA256, self.root, "x86_64",
                "hypopg-linux-selected-18.0-{run_id}")

    def test_accepts_arm64_candidate_and_rejects_wrong_architecture(self):
        self.write_candidate(artifact_name="linux-publication-arm64-evidence", architecture="arm64")
        result = candidate.validate_candidate(
            self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
            self.BUILDER_PACKAGES_SHA256, self.root, "arm64")
        self.assertEqual(result["run_id"], "1234")
        with self.assertRaisesRegex(ValueError, "target"):
            candidate.validate_candidate(
                self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
                self.BUILDER_PACKAGES_SHA256, self.root, "x86_64")

    def test_rejects_selected_artifact_with_mismatched_version_or_run(self):
        for name in ("pgvector-linux-selected-18.0-1234", "pgvector-linux-selected-17.11-9876"):
            with self.subTest(name=name):
                self.write_candidate(artifact_name=name)
                with self.assertRaisesRegex(ValueError, "artifact identity"):
                    candidate.validate_candidate(
                        self.manifest_path, self.archive_path, "17.11", self.BASE_IMAGE_DIGEST,
                        self.BUILDER_PACKAGES_SHA256, self.root)


if __name__ == "__main__":
    unittest.main()
