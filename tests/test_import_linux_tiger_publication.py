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
import import_linux_tiger_publication as importer


class LinuxTigerPublicationImportTests(unittest.TestCase):
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
        for profile_id in ("tiger-publication-current-x86_64",
                           "tiger-publication-minimum-x86_64"):
            source_paths.update(profiles[profile_id]["sources"])
        for source in source_paths:
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / source, destination)

        self.core_artifact = base / "core-artifact"
        self.postgis_artifact = base / "postgis-artifact"
        self.tiger_artifact = base / "tiger-artifact"
        self.core_dir = self.core_artifact / "pilot"
        self.postgis_dir = self.postgis_artifact / "postgis"
        self.tiger_dir = self.tiger_artifact / "tiger"
        for directory in (self.core_dir, self.postgis_dir, self.tiger_dir):
            directory.mkdir(parents=True)
        self.run_id = "7654321"
        self.architecture = "x86_64"
        self.platform = "linux-x86_64"
        self.core_name = f"postgresql-18.6-{self.platform}.tar.gz"
        self.postgis_name = f"postgis-3.6.4-postgresql-18.6-{self.platform}.tar.gz"
        self.tiger_name = f"postgis_tiger_geocoder-2025.2-postgresql-18.6-{self.platform}.tar.gz"
        self._archive(self.core_dir / self.core_name, b"core")
        self._metadata_archive(self.postgis_dir / self.postgis_name, {
            "project": "postgis", "version": "3.6.4", "postgresql_version": "18.6",
            "platform": "linux", "architecture": "x86_64",
            "sql_names": ["postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology"],
        })
        self._metadata_archive(self.tiger_dir / self.tiger_name, {
            "project": "postgis_tiger_geocoder", "version": "2025.2",
            "postgresql_version": "18.6", "platform": "linux", "architecture": "x86_64",
            "sql_names": ["postgis_tiger_geocoder"], "requires": ["PostGIS"],
        })
        for directory, name in ((self.core_dir, self.core_name),
                                (self.postgis_dir, self.postgis_name),
                                (self.tiger_dir, self.tiger_name)):
            path = directory / name
            (directory / f"{name}.sha256").write_text(f"{self._sha(path)}  {name}\n")
        self.publication = self.tiger_artifact / "tiger-publication"
        self.records_dir = self.publication / "records"
        self.records_dir.mkdir(parents=True)
        self._make_records()
        qemu = self.tiger_artifact / "tiger-qemu/evidence"
        qemu.mkdir(parents=True)
        self._write_guest_checksums(qemu / "archive-checksums.sha256")
        (qemu / "environment.txt").write_text(
            f"test_revision={'a' * 40}\nimage_sha256={'b' * 64}\n")
        (qemu / "full-verifier.log").write_text(
            "guest_os=Ubuntu 22.04.5 LTS\n"
            "guest_kernel=5.15.0-1109-kvm\n"
            "guest_architecture=x86_64\n"
            "PASS: TIGER Geocoder 2025.2 minimum-kernel archive verification\n")

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

    def _write_guest_checksums(self, path):
        values = []
        for directory, name in ((self.core_dir, self.core_name),
                                (self.postgis_dir, self.postgis_name),
                                (self.tiger_dir, self.tiger_name)):
            values.append(f"{self._sha(directory / name)}  {name}")
        path.write_text("\n".join(values) + "\n")

    def _make_records(self, result="success"):
        postgis_sha = self._sha(self.postgis_dir / self.postgis_name)
        core_sha = self._sha(self.core_dir / self.core_name)
        tiger_sha = self._sha(self.tiger_dir / self.tiger_name)
        for endpoint, profile_id, kernel, distribution, distribution_version in (
                ("current", "tiger-publication-current-x86_64", "6.8.0", "Ubuntu 24.04", "24.04"),
                ("minimum", "tiger-publication-minimum-x86_64", "5.15.0-1109-kvm",
                 "Ubuntu 22.04.5 LTS", "22.04")):
            raw_result = {"failed": "failure"}.get(result, result)
            self._write_json(self.publication / f"{endpoint}-steps.json", {"archive-suite": raw_result})
            profile = coverage.verification_profile(self.root, profile_id)
            receipt = {
                "profile_id": profile_id, "profile_revision": profile["profile_revision"],
                "test_revision": "a" * 40, "project": "PostGIS TIGER Geocoder",
                "version": "2025.2", "postgresql_version": "18.6", "architecture": "x86_64",
                "endpoint": endpoint, "kernel_release": kernel,
                "distribution": distribution, "distribution_version": distribution_version,
                "image_id": "sha256:" + "b" * 64, "clean_system": result == "success",
                "dependency_check_profile": "postgis_tiger_geocoder-runtime-v1",
                "dependency_checks_passed": result == "success",
                "case_results": {"archive-suite": {"success": "passed", "failed": "failed",
                                                         "skipped": "skipped"}[result]},
                "extension_archive": self.tiger_name,
                "archives": {self.tiger_name: tiger_sha, self.core_name: core_sha},
                "prerequisite_archives": [{"project": "PostGIS", "archive": self.postgis_name,
                                             "version": "3.6.4", "sha256": postgis_sha}],
                "ci": {"provider": "github-actions", "run_id": self.run_id,
                       "run_url": f"https://github.com/example/repo/actions/runs/{self.run_id}",
                       "source_revision": "a" * 40, "test_revision": "a" * 40,
                       "build_revision": "a" * 40},
            }
            receipt_path = self.publication / f"{endpoint}-receipt.json"
            self._write_json(receipt_path, receipt)
            outputs = emitter.emit(self.root, self.tiger_dir, self.core_dir, receipt_path,
                                   self.records_dir, {"PostGIS": self.postgis_dir / self.postgis_name})
            if result != "success":
                # The emitter produces retained failed/skipped records with non-passing claims.
                self.assertEqual(json.loads(outputs[0].read_text())["outcome"],
                                 {"failed": "failed", "skipped": "skipped"}[result])

    @staticmethod
    def _write_json(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def test_imports_records_and_compact_evidence_after_checksum_validation(self):
        retained = importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                       self.tiger_artifact, self.run_id, self.architecture)
        self.assertEqual(len(retained), 9)
        record = self.root / "support/verification" / (
            f"postgis_tiger_geocoder-2025.2-postgresql-18.6-{self.platform}-current-{self.run_id}.json")
        self.assertEqual(json.loads(record.read_text())["outcome"], "passed")
        steps = self.root / "support/evidence" / f"tiger-publication-{self.run_id}/x86_64/current-steps.json"
        self.assertTrue(steps.is_file())
        self.assertTrue((steps.parent / "qemu/archive-checksums.sha256").is_file())
        compressed = steps.parent / "qemu/full-verifier.log.gz"
        self.assertEqual(importer.gzip.decompress(compressed.read_bytes()),
                         (self.tiger_artifact / "tiger-qemu/evidence/full-verifier.log").read_bytes())
        first_bytes = compressed.read_bytes()
        importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                            self.tiger_artifact, self.run_id, self.architecture)
        self.assertEqual(compressed.read_bytes(), first_bytes)

    def test_retains_failed_and_skipped_steps_when_records_are_absent(self):
        for result in ("failed", "skipped"):
            with self.subTest(result=result):
                shutil.rmtree(self.root / "support/evidence", ignore_errors=True)
                (self.root / "support/evidence").mkdir()
                shutil.rmtree(self.root / "support/verification", ignore_errors=True)
                (self.root / "support/verification").mkdir()
                self._make_records(result)
                for path in self.records_dir.glob("*.json"):
                    path.unlink()
                retained = importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                               self.tiger_artifact, self.run_id, self.architecture)
                self.assertGreaterEqual(len(retained), 2)
                saved = json.loads((self.root / "support/evidence" /
                                    f"tiger-publication-{self.run_id}/x86_64/minimum-steps.json").read_text())
                self.assertEqual(saved, {"archive-suite": "failure" if result == "failed" else result})

    def test_retains_raw_outcomes_when_archives_and_records_are_absent(self):
        for path in self.records_dir.glob("*.json"):
            path.unlink()
        for endpoint in ("current", "minimum"):
            (self.publication / f"{endpoint}-receipt.json").unlink()
        (self.core_dir / self.core_name).unlink()
        retained = importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                       self.tiger_artifact, self.run_id, self.architecture)
        self.assertEqual(len(retained), 2)
        self.assertTrue((self.root / "support/evidence" / f"tiger-publication-{self.run_id}/x86_64/current-steps.json").is_file())

    def test_missing_archives_with_any_record_is_an_error(self):
        (self.core_dir / self.core_name).unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "records exist.*archives are missing"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.tiger_artifact, self.run_id, self.architecture)

    def test_passed_minimum_record_requires_matching_guest_proof(self):
        log = self.tiger_artifact / "tiger-qemu/evidence/full-verifier.log"
        log.write_text(log.read_text().replace("guest_architecture=x86_64", "guest_architecture=arm64"))
        with self.assertRaisesRegex(coverage.CoverageError, "guest log"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.tiger_artifact, self.run_id, self.architecture)

    def test_passed_minimum_record_requires_matching_guest_image_checksum(self):
        environment = self.tiger_artifact / "tiger-qemu/evidence/environment.txt"
        environment.write_text(environment.read_text().replace("b" * 64, "c" * 64))
        with self.assertRaisesRegex(coverage.CoverageError, "image checksum does not match"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.tiger_artifact, self.run_id, self.architecture)

    def test_rejects_archive_sidecar_and_prerequisite_checksum_mismatch(self):
        sidecar = self.core_dir / f"{self.core_name}.sha256"
        sidecar.write_text("0" * 64 + f"  {self.core_name}\n")
        with self.assertRaisesRegex(coverage.CoverageError, "sidecar"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.tiger_artifact, self.run_id, self.architecture)
        sidecar.write_text(f"{self._sha(self.core_dir / self.core_name)}  {self.core_name}\n")
        record = next(self.records_dir.glob("*.json"))
        data = json.loads(record.read_text())
        data["prerequisite_archives"][0]["sha256"] = "0" * 64
        record.write_text(json.dumps(data))
        with self.assertRaisesRegex(coverage.CoverageError, "prerequisite PostGIS checksum"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.tiger_artifact, self.run_id, self.architecture)

    def test_rejects_stale_profile_and_step_outcome_disagreement(self):
        record = next(self.records_dir.glob("*-current-*.json"))
        data = json.loads(record.read_text())
        data["profile_revision"] = "0" * 64
        record.write_text(json.dumps(data))
        with self.assertRaisesRegex(coverage.CoverageError, "test profile"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.tiger_artifact, self.run_id, self.architecture)


if __name__ == "__main__":
    unittest.main()
