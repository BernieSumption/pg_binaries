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
import emit_extension_publication_records as emitter
import import_linux_hypopg_publication as importer


class LinuxHypopgPublicationImportTests(unittest.TestCase):
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
        for profile_id in ("hypopg-publication-current-x86_64",):
            source_paths.update(profiles[profile_id]["sources"])
        for profile_source in source_paths:
            source = profile_source.partition("#profile-section=")[0]
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / source, destination)

        self.core_artifact = base / "core-artifact"
        self.hypopg_artifact = base / "hypopg-artifact"
        self.core_dir = self.core_artifact / "pilot"
        self.hypopg_dir = self.hypopg_artifact / "hypopg"
        for directory in (self.core_dir, self.hypopg_dir):
            directory.mkdir(parents=True)
        self.run_id = "7654321"
        self.architecture = "x86_64"
        self.platform = "linux-x86_64"
        self.postgresql_version = "18.6"
        self._make_archives()
        self.publication = self.hypopg_artifact / "hypopg-publication"
        self.records_dir = self.publication / "records"
        self.records_dir.mkdir(parents=True)
        self._make_records()

    def _make_archives(self):
        self.core_name = f"postgresql-{self.postgresql_version}-{self.platform}.tar.gz"
        self.hypopg_name = f"hypopg-1.4.3-postgresql-{self.postgresql_version}-{self.platform}.tar.gz"
        self._archive(self.core_dir / self.core_name, b"core")
        self._metadata_archive(self.hypopg_dir / self.hypopg_name, {
            "project": "hypopg", "version": "1.4.3",
            "postgresql_version": self.postgresql_version, "platform": "linux", "architecture": "x86_64",
            "sql_names": ["hypopg"], "requires": [],
        })
        for directory, name in ((self.core_dir, self.core_name),
                                (self.hypopg_dir, self.hypopg_name)):
            path = directory / name
            (directory / f"{name}.sha256").write_text(f"{self._sha(path)}  {name}\n")
        analysis = self.hypopg_dir / "static-analysis/hypopg.json"
        analysis.parent.mkdir(parents=True)
        analysis.write_text(json.dumps({"outcome": "passed", "architecture": self.architecture,
            "files": [{"path": "metadata.json", "architecture": self.architecture,
                       "interpreter": "none", "runtime_search_paths": []}], "archives": [
                {"basename": name, "sha256": self._sha(directory / name)}
                for directory, name in ((self.core_dir, self.core_name),
                                        (self.hypopg_dir, self.hypopg_name))]}))

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _archive(path, data):
        path.write_bytes(data)

    @staticmethod
    def _metadata_archive(path, metadata):
        temporary = path.with_suffix(".json")
        temporary.write_text(json.dumps(metadata))
        with tarfile.open(path, "w:gz") as archive:
            archive.add(temporary, arcname="metadata.json")
        temporary.unlink()

    def _make_records(self, result="success"):
        core_sha = self._sha(self.core_dir / self.core_name)
        hypopg_sha = self._sha(self.hypopg_dir / self.hypopg_name)
        for endpoint, profile_id, kernel, distribution, distribution_version in (
                ("current", "hypopg-publication-current-x86_64", "6.8.0-test-kernel", "Alpine Linux", "3.22.6"),):
            raw_result = {"failed": "failure"}.get(result, result)
            self._write_json(self.publication / f"{endpoint}-steps.json", {"archive-suite": raw_result})
            profile = coverage.verification_profile(self.root, profile_id)
            receipt = {
                "profile_id": profile_id, "profile_revision": profile["profile_revision"],
                "test_revision": "a" * 40, "project": "HypoPG",
                "version": "1.4.3", "postgresql_version": self.postgresql_version, "architecture": "x86_64",
                "endpoint": endpoint, "kernel_release": kernel,
                "distribution": distribution, "distribution_version": distribution_version,
                "image_id": "sha256:" + "b" * 64, "clean_system": result == "success",
                "dependency_check_profile": "hypopg-runtime-v1",
                "dependency_checks_passed": result == "success",
                "case_results": {"archive-suite": {"success": "passed", "failed": "failed",
                                                         "skipped": "skipped"}[result]},
                "extension_archive": self.hypopg_name,
                "archives": {self.hypopg_name: hypopg_sha, self.core_name: core_sha},
                "prerequisite_archives": [],
                "ci": {"provider": "github-actions", "run_id": self.run_id,
                       "run_url": f"https://github.com/example/repo/actions/runs/{self.run_id}",
                       "source_revision": "a" * 40, "test_revision": "a" * 40,
                       "build_revision": "a" * 40},
            }
            receipt_path = self.publication / f"{endpoint}-receipt.json"
            self._write_json(receipt_path, receipt)
            outputs = emitter.emit(self.root, self.hypopg_dir, self.core_dir, receipt_path,
                                   self.records_dir)
            if result != "success":
                # The emitter produces retained failed/skipped records with non-passing claims.
                self.assertEqual(json.loads(outputs[0].read_text())["outcome"],
                                 {"failed": "failed", "skipped": "skipped"}[result])

    @staticmethod
    def _write_json(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def _import(self):
        return importer.import_run(self.root, self.core_artifact, self.hypopg_artifact,
                                   self.run_id, self.architecture, self.postgresql_version)

    def test_retains_selected_pg15_core(self):
        shutil.rmtree(self.core_dir)
        shutil.rmtree(self.hypopg_dir)
        shutil.rmtree(self.publication)
        self.core_dir.mkdir()
        self.hypopg_dir.mkdir()
        self.records_dir.mkdir(parents=True)
        self.postgresql_version = "15.19"
        self._make_archives()
        self._make_records()
        retained = self._import()
        record = json.loads((self.root / "support/verification" /
            f"hypopg-1.4.3-postgresql-15.19-{self.platform}-current-{self.run_id}.json").read_text())
        self.assertEqual(record["postgresql_version"], "15.19")
        self.assertEqual(record["assembled_core"]["archive"], self.core_name)
        self.assertEqual(len(retained), 4)

    def test_retains_exact_bytes_and_is_idempotent(self):
        log = self.publication / "current-verifier.log"
        log.write_bytes(b"verifier output\n")
        retained = self._import()
        self.assertEqual(len(retained), 5)
        for source in [self.publication / "current-receipt.json", log]:
            destination = self.root / "support/evidence" / f"hypopg-publication-{self.run_id}/x86_64" / source.name
            self.assertEqual(source.read_bytes(), destination.read_bytes())
        self.assertEqual(self._import(), retained)

    def test_rejects_receipt_archive_mismatch_without_writing(self):
        path = self.publication / "current-receipt.json"
        receipt = json.loads(path.read_text())
        receipt["archives"][self.core_name] = "0" * 64
        self._write_json(path, receipt)
        with self.assertRaisesRegex(coverage.CoverageError, "receipt identity"):
            self._import()
        self.assertFalse((self.root / "support/evidence").exists())

    def test_rejects_tampered_extension_checksum_sidecar(self):
        sidecar = self.hypopg_dir / f"{self.hypopg_name}.sha256"
        sidecar.write_text("0" * 64 + f"  {self.hypopg_name}\n")
        with self.assertRaisesRegex(coverage.CoverageError, "checksum sidecar does not match"):
            self._import()
        self.assertFalse((self.root / "support/evidence").exists())

    def test_rejects_missing_archives_and_receipt(self):
        (self.publication / "current-receipt.json").unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "matching receipt"):
            self._import()
        (self.core_dir / self.core_name).unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "archives are missing"):
            self._import()

    def test_rejects_missing_report_for_passed_run(self):
        (self.hypopg_dir / "static-analysis/hypopg.json").unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "requires a static-analysis"):
            self._import()

    def test_failed_and_skipped_records_remain_non_passing(self):
        for result in ("failed", "skipped"):
            with self.subTest(result=result):
                shutil.rmtree(self.root / "support/evidence", ignore_errors=True)
                shutil.rmtree(self.root / "support/verification", ignore_errors=True)
                self._make_records(result)
                self._import()
                retained = next((self.root / "support/verification").glob("*.json"))
                self.assertEqual(json.loads(retained.read_text())["outcome"], result)

    def test_rejects_static_archive_claim_mismatch(self):
        path = self.hypopg_dir / "static-analysis/hypopg.json"
        report = json.loads(path.read_text())
        report["archives"][0]["sha256"] = "0" * 64
        self._write_json(path, report)
        with self.assertRaisesRegex(coverage.CoverageError, "archives do not match"):
            self._import()
        self.assertFalse((self.root / "support/evidence").exists())

    def test_failed_build_retains_raw_outcome(self):
        shutil.rmtree(self.records_dir)
        (self.publication / "current-receipt.json").unlink()
        (self.core_dir / self.core_name).unlink()
        (self.hypopg_dir / "static-analysis/hypopg.json").unlink()
        self._write_json(self.publication / "current-steps.json", {"archive-suite": "skipped"})
        self.assertEqual(len(self._import()), 1)

    def test_conflict_and_oversize_log_do_not_leave_partial_evidence(self):
        log = self.publication / "verifier.log"
        log.write_bytes(b"x" * (importer.MAX_EVIDENCE_BYTES + 1))
        with self.assertRaisesRegex(coverage.CoverageError, "at most"):
            self._import()
        self.assertFalse((self.root / "support/evidence").exists())
        log.unlink()
        self._import()
        self._write_json(self.publication / "current-steps.json", {"archive-suite": "failure"})
        with self.assertRaises(coverage.CoverageError):
            self._import()


if __name__ == "__main__":
    unittest.main()
