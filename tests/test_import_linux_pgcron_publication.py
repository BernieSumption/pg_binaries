import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import coverage
import create_extension_publication_receipt as receipt_creator
import emit_extension_publication_records as emitter
import import_linux_pgcron_publication as importer


class LinuxPgcronPublicationImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.root = base / "root"
        (self.root / "support").mkdir(parents=True)
        for source in ("support.json", "support/verification-profiles.json",
                       "support/postgresql-releases.json"):
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / source, destination)
        profiles = coverage.load_json(self.root / "support/verification-profiles.json")["profiles"]
        source_paths = set()
        for profile_id in ("pgcron-publication-linux-x86_64-15.19",
                           "pgcron-publication-linux-x86_64-18.6",
                           "pgcron-publication-linux-arm64-18.6"):
            source_paths.update(profiles[profile_id]["sources"])
        for profile_source in source_paths:
            source = profile_source.partition("#profile-section=")[0]
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / source, destination)

        self.base = base
        self.run_id = "7654321"
        self.postgresql_version = "18.6"
        self.architecture = "x86_64"
        self.pgcron_version = self._selected_version(self.postgresql_version)
        self.case_id = "pgcron-archive-suite"
        self._make_artifacts()
        self._make_publication()

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def _selected_version(self, postgresql_version):
        support = coverage.load_json(self.root / "support.json")
        releases = coverage.release_snapshot(
            coverage.load_json(self.root / "support/postgresql-releases.json"), support)
        return importer._selected_version(
            support, releases, postgresql_version, f"linux-{self.architecture}")

    @classmethod
    def _archive(cls, path, metadata):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(path, "w:gz") as archive:
            data = json.dumps(metadata).encode()
            from io import BytesIO
            member = tarfile.TarInfo("metadata.json")
            member.size = len(data)
            archive.addfile(member, BytesIO(data))
        path.with_name(path.name + ".sha256").write_text(
            f"{cls._sha(path)}  {path.name}\n", encoding="utf-8")

    def _make_artifacts(self):
        self.core_artifact = self.base / "core-artifact"
        self.pgcron_artifact = self.base / "pgcron-artifact"
        self.core_dir = self.core_artifact / "pilot"
        self.pgcron_dir = self.pgcron_artifact / "pg_cron"
        self.core_dir.mkdir(parents=True, exist_ok=True)
        self.pgcron_dir.mkdir(parents=True, exist_ok=True)
        self.platform = f"linux-{self.architecture}"
        self.core_name = f"postgresql-{self.postgresql_version}-{self.platform}.tar.gz"
        self.pgcron_name = f"pg_cron-{self.pgcron_version}-postgresql-{self.postgresql_version}-{self.platform}.tar.gz"
        self._archive(self.core_dir / self.core_name, {"archive": "core"})
        self._archive(self.pgcron_dir / self.pgcron_name, {
            "project": "pg_cron", "version": self.pgcron_version, "postgresql_version": self.postgresql_version,
            "platform": "linux", "architecture": self.architecture,
            "sql_names": ["pg_cron"], "requires": [],
        })
        report = self.pgcron_dir / "static-analysis/pg_cron.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({
            "outcome": "passed", "architecture": self.architecture,
            "files": [{"path": "pg_cron/lib/pg_cron.so", "architecture": self.architecture,
                       "interpreter": "none", "runtime_search_paths": []}],
            "archives": [
                {"basename": self.core_name, "sha256": self._sha(self.core_dir / self.core_name)},
                {"basename": self.pgcron_name, "sha256": self._sha(self.pgcron_dir / self.pgcron_name)},
            ],
        }))

    def _make_publication(self, result="success"):
        self.publication = self.pgcron_artifact / "pgcron-publication"
        self.records_dir = self.publication / "records"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        profile_id = f"pgcron-publication-linux-{self.architecture}-{self.postgresql_version}"
        profile = coverage.verification_profile(self.root, profile_id)
        image = "sha256:" + "b" * 64
        step_outcomes = {
            "success": {"core_build": "success", "pgcron_build": "success", "pgcron_verify": "success"},
            "failed": {"core_build": "success", "pgcron_build": "success", "pgcron_verify": "failure"},
            "skipped": {"core_build": "success", "pgcron_build": "skipped", "pgcron_verify": "skipped"},
        }[result]
        suite = {"success": "success", "failed": "failure", "skipped": "skipped"}[result]
        attempt_path = self.publication / "attempt.json"
        attempt_path.write_text(json.dumps({
            "schema_version": 1, "run_id": self.run_id, "source_revision": "a" * 40,
            "postgresql_version": self.postgresql_version, "pg_cron_version": self.pgcron_version,
            "architecture": self.architecture, "verifier_image_id": image,
            "steps": step_outcomes,
        }))
        steps_path = self.publication / "current-steps.json"
        steps_path.write_text(json.dumps({self.case_id: suite}))
        receipt_path = self.publication / "current-receipt.json"
        receipt_creator.create(
            self.root, self.pgcron_dir, self.core_dir, receipt_path, profile_id,
            "pg_cron", self.pgcron_version, self.postgresql_version, self.postgresql_version,
            self.architecture, "current", "6.8.0-test-kernel", "Alpine Linux", "3.22.6",
            image, "success" if result == "success" else "failure", result == "success",
            steps_path, environ={
                "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": self.run_id,
                "GITHUB_REPOSITORY": "example/repo", "GITHUB_SERVER_URL": "https://github.com",
            })
        emitter.emit(self.root, self.pgcron_dir, self.core_dir, receipt_path, self.records_dir)

    def _import(self):
        return importer.import_run(self.root, self.core_artifact, self.pgcron_artifact,
                                   self.run_id, self.architecture, self.postgresql_version)

    def test_retains_exact_archive_bound_evidence_idempotently(self):
        retained = importer.import_run(self.root, self.core_artifact, self.pgcron_artifact,
                                        self.run_id, self.architecture)
        record_path = self.root / "support/verification" / (
            f"pg_cron-{self.pgcron_version}-postgresql-{self.postgresql_version}-{self.platform}-current-{self.run_id}.json")
        record = json.loads(record_path.read_text())
        self.assertEqual(record["assembled_core"]["sha256"], self._sha(self.core_dir / self.core_name))
        self.assertEqual(record["sha256"], self._sha(self.pgcron_dir / self.pgcron_name))
        self.assertEqual(len(retained), 5)
        self.assertEqual(self._import(), retained)

    def test_imports_arm64_profile_and_archive_names(self):
        self.architecture = "arm64"
        shutil.rmtree(self.pgcron_artifact / "pgcron-publication")
        self._make_artifacts()
        self._make_publication()
        self._import()
        record_path = self.root / "support/verification" / (
            f"pg_cron-{self.pgcron_version}-postgresql-18.6-linux-arm64-current-{self.run_id}.json")
        self.assertEqual(json.loads(record_path.read_text())["platform"], "linux-arm64")

    def test_retains_failed_and_skipped_archive_records_as_nonpassing(self):
        for result in ("failed", "skipped"):
            with self.subTest(result=result):
                shutil.rmtree(self.root / "support/evidence", ignore_errors=True)
                shutil.rmtree(self.root / "support/verification", ignore_errors=True)
                shutil.rmtree(self.records_dir)
                self._make_publication(result)
                self._import()
                record = json.loads(next((self.root / "support/verification").glob("*.json")).read_text())
                self.assertEqual(record["outcome"], result)

    def test_retains_raw_attempt_when_archives_are_unavailable(self):
        for archive in (self.core_dir / self.core_name, self.pgcron_dir / self.pgcron_name):
            archive.unlink()
            archive.with_name(archive.name + ".sha256").unlink()
        (self.pgcron_dir / "static-analysis/pg_cron.json").unlink()
        shutil.rmtree(self.records_dir)
        (self.publication / "current-receipt.json").unlink()
        (self.publication / "current-steps.json").write_text(
            json.dumps({self.case_id: "skipped"}))
        attempt = json.loads((self.publication / "attempt.json").read_text())
        attempt["steps"] = {"core_build": "failure", "pgcron_build": "skipped", "pgcron_verify": "skipped"}
        (self.publication / "attempt.json").write_text(json.dumps(attempt))
        self.assertEqual(len(self._import()), 2)

    def test_rejects_core_checksum_and_profile_revision_mismatches(self):
        receipt_path = self.publication / "current-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["archives"][self.core_name] = "0" * 64
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(coverage.CoverageError, "receipt identity"):
            self._import()
        receipt["archives"][self.core_name] = self._sha(self.core_dir / self.core_name)
        receipt["profile_revision"] = "0" * 64
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(coverage.CoverageError, "receipt identity"):
            self._import()
        self.assertFalse((self.root / "support/evidence").exists())

    def test_rejects_record_profile_revision_that_differs_from_receipt(self):
        path = next(self.records_dir.glob("*.json"))
        record = json.loads(path.read_text())
        record["profile_revision"] = "0" * 64
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(coverage.CoverageError, "profile"):
            self._import()

    def test_rejects_missing_or_bad_sidecars(self):
        sidecar = self.pgcron_dir / f"{self.pgcron_name}.sha256"
        original = sidecar.read_text()
        sidecar.unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "sidecar"):
            self._import()
        sidecar.write_text("0" * 64 + "  " + self.pgcron_name + "\n")
        with self.assertRaisesRegex(coverage.CoverageError, "checksum"):
            self._import()
        sidecar.write_text(original)

    def test_rejects_non_alpine_or_mismatched_verifier_identity(self):
        path = self.publication / "current-receipt.json"
        receipt = json.loads(path.read_text())
        receipt["distribution"] = "Ubuntu"
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(coverage.CoverageError, "Alpine 3.22"):
            self._import()
        receipt["distribution"] = "Alpine Linux"
        receipt["image_id"] = "sha256:" + "b" * 64
        receipt["kernel_release"] = "6.8.0-different-kernel"
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(coverage.CoverageError, "record identity"):
            self._import()
        receipt["kernel_release"] = "6.8.0-test-kernel"
        receipt["image_id"] = "sha256:" + "c" * 64
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(coverage.CoverageError, "Alpine 3.22"):
            self._import()

    def test_rejects_missing_or_mismatched_static_analysis_for_passed_run(self):
        report = self.pgcron_dir / "static-analysis/pg_cron.json"
        original = report.read_text()
        report.unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "requires a static-analysis"):
            self._import()
        data = json.loads(original)
        data["archives"][0]["sha256"] = "0" * 64
        report.write_text(json.dumps(data))
        with self.assertRaisesRegex(coverage.CoverageError, "static-analysis archives do not match"):
            self._import()

    def test_imports_an_explicit_selected_postgresql_minor(self):
        self.postgresql_version = "17.11"
        self.pgcron_version = self._selected_version(self.postgresql_version)
        shutil.rmtree(self.pgcron_artifact)
        shutil.rmtree(self.core_artifact)
        self._make_artifacts()
        shutil.rmtree(self.pgcron_artifact / "pgcron-publication", ignore_errors=True)
        self._make_publication()
        retained = self._import()
        record = self.root / "support/verification" / (
            f"pg_cron-{self.pgcron_version}-postgresql-17.11-{self.platform}-current-{self.run_id}.json")
        self.assertIn(str(record.relative_to(self.root)), retained)
        data = json.loads(record.read_text())
        self.assertEqual(data["assembled_core"]["archive"], self.core_name)
        self.assertEqual(data["assembled_core"]["sha256"], self._sha(self.core_dir / self.core_name))

    def test_same_run_retains_each_postgresql_target_separately(self):
        self._import()
        self.postgresql_version = "15.19"
        self.pgcron_version = self._selected_version(self.postgresql_version)
        shutil.rmtree(self.pgcron_artifact)
        shutil.rmtree(self.core_artifact)
        self._make_artifacts()
        self._make_publication()
        self._import()
        evidence = self.root / "support/evidence" / f"pgcron-publication-{self.run_id}/x86_64"
        self.assertTrue((evidence / "18.6/current-receipt.json").is_file())
        self.assertTrue((evidence / "15.19/current-receipt.json").is_file())

    def test_rejects_unselected_postgresql_minor(self):
        with self.assertRaisesRegex(coverage.CoverageError, "18.5 is not selected"):
            importer.import_run(self.root, self.core_artifact, self.pgcron_artifact,
                                self.run_id, self.architecture, "18.5")


if __name__ == "__main__":
    unittest.main()
