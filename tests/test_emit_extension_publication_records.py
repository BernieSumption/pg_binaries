import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
import create_extension_publication_receipt as receipt_creator
import emit_extension_publication_records as emitter


REPO = Path(__file__).resolve().parents[1]


class ExtensionPublicationRecordTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.root = base / "root"
        self.archives = base / "extensions"
        self.core_archives = base / "core"
        self.output = base / "records"
        (self.root / "support").mkdir(parents=True)
        self.archives.mkdir()
        self.core_archives.mkdir()
        shutil.copy(REPO / "support.json", self.root / "support.json")
        shutil.copy(REPO / "support/postgresql-releases.json",
                    self.root / "support/postgresql-releases.json")
        (self.root / "verifier.txt").write_text("TIGER verifier source\n")
        self.profile_id = "extension-publication-test"
        (self.root / "support/verification-profiles.json").write_text(json.dumps({
            "schema_version": 1, "profiles": {self.profile_id: {
                "scope": "publication", "platforms": ["linux-x86_64"],
                "case_ids": ["archive-assembly", "tiger-normalize"],
                "sources": ["verifier.txt"],
            }},
        }))
        self.core_name = "postgresql-18.6-linux-x86_64.tar.gz"
        self.extension_name = "postgis_tiger_geocoder-2025.2-postgresql-18.6-linux-x86_64.tar.gz"
        self.metadata = {
            "project": "postgis_tiger_geocoder", "version": "2025.2",
            "postgresql_version": "18.6", "platform": "linux", "architecture": "x86_64",
            "sql_names": ["postgis_tiger_geocoder"],
            "requires": ["PostGIS"], "configuration_prerequisites": [],
            "runtime_prerequisites": [],
        }
        self._write_extension()
        (self.core_archives / self.core_name).write_bytes(b"core archive fixture")
        self.receipt = {
            "profile_id": self.profile_id,
            "profile_revision": coverage.verification_profile(
                self.root, self.profile_id)["profile_revision"],
            "test_revision": "a" * 40, "project": "PostGIS TIGER Geocoder",
            "version": "2025.2", "postgresql_version": "18.6", "architecture": "x86_64",
            "endpoint": "minimum", "kernel_release": "5.15.0-1109-kvm",
            "distribution": "Ubuntu 22.04.5 LTS", "distribution_version": "22.04",
            "image_id": "sha256:" + "b" * 64, "clean_system": True,
            "dependency_check_profile": "postgis_tiger_geocoder-runtime-v1",
            "dependency_checks_passed": True,
            "case_results": {"archive-assembly": "passed", "tiger-normalize": "passed"},
            "extension_archive": self.extension_name, "archives": {},
            "ci": {"provider": "github-actions", "run_id": "987",
                   "run_url": "https://github.com/o/r/actions/runs/987",
                   "source_revision": "a" * 40, "build_revision": "a" * 40,
                   "test_revision": "a" * 40},
        }
        self._write_checksums()
        self.receipt_path = base / "receipt.json"
        self._write_receipt()

    def tearDown(self):
        self.temporary.cleanup()

    def _write_extension(self):
        path = self.archives / self.extension_name
        with tarfile.open(path, "w:gz") as archive:
            data = json.dumps(self.metadata).encode()
            member = tarfile.TarInfo("metadata.json")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))

    def _write_checksums(self):
        for name, directory in ((self.core_name, self.core_archives),
                                (self.extension_name, self.archives)):
            digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
            self.receipt["archives"][name] = digest
            (directory / f"{name}.sha256").write_text(f"{digest}  {name}\n")

    def _write_receipt(self):
        self.receipt_path.write_text(json.dumps(self.receipt))

    def emit(self):
        self._write_receipt()
        return emitter.emit(self.root, self.archives, self.core_archives,
                            self.receipt_path, self.output)

    def test_emits_publication_record_for_declared_sql_name(self):
        paths = self.emit()
        self.assertEqual(len(paths), 1)
        record = json.loads(paths[0].read_text())
        self.assertEqual(record["component"], "postgis_tiger_geocoder")
        self.assertEqual(record["project"], "PostGIS TIGER Geocoder")
        self.assertEqual(record["assembled_core"]["sha256"],
                         self.receipt["archives"][self.core_name])
        self.assertEqual(record["sha256"], self.receipt["archives"][self.extension_name])
        self.assertEqual(record["environment"]["os_version"], "5.15.0")
        coverage.validate_verification_record(
            record, coverage.load_json(self.root / "support.json"), self.root)

    def test_rejects_mismatched_core_or_extension_checksum(self):
        for name in (self.core_name, self.extension_name):
            with self.subTest(archive=name):
                original = self.receipt["archives"][name]
                self.receipt["archives"][name] = "0" * 64
                with self.assertRaisesRegex(coverage.CoverageError, "checksum does not match"):
                    self.emit()
                self.receipt["archives"][name] = original

    def test_rejects_stale_profile_and_missing_case(self):
        original = self.receipt["profile_revision"]
        self.receipt["profile_revision"] = "0" * 64
        with self.assertRaisesRegex(coverage.CoverageError, "stale"):
            self.emit()
        self.receipt["profile_revision"] = original
        self.receipt["case_results"].pop("tiger-normalize")
        with self.assertRaisesRegex(coverage.CoverageError, "exactly the registered cases"):
            self.emit()

    def test_records_failed_and_skipped_cases_without_passing_claim(self):
        for result in ("failed", "skipped"):
            with self.subTest(result=result):
                self.receipt["case_results"]["tiger-normalize"] = result
                self.receipt["clean_system"] = False
                self.receipt["dependency_checks_passed"] = False
                record = json.loads(self.emit()[0].read_text())
                self.assertEqual(record["outcome"], result)
                self.assertFalse(record["environment"]["clean_system"])

    def test_rejects_metadata_build_target_mismatch(self):
        self.metadata["postgresql_version"] = "17.11"
        self._write_extension()
        self._write_checksums()
        with self.assertRaisesRegex(coverage.CoverageError, "does not match its filename"):
            self.emit()

    def test_rejects_wrong_endpoint_and_unpinned_passing_image(self):
        self.receipt["kernel_release"] = "5.14.9"
        with self.assertRaisesRegex(coverage.CoverageError, "Linux kernel 5.15"):
            self.emit()
        self.receipt["kernel_release"] = "5.15.0-1109-kvm"
        self.receipt["image_id"] = "ubuntu-22.04"
        with self.assertRaisesRegex(coverage.CoverageError, "image digest"):
            self.emit()

    def test_rejects_unverified_build_revision(self):
        self.receipt["ci"]["build_revision"] = "c" * 40
        with self.assertRaisesRegex(coverage.CoverageError, "revision provenance"):
            self.emit()

    def test_rejects_unrelated_dependency_profile(self):
        self.receipt["dependency_check_profile"] = "other-runtime-v1"
        with self.assertRaisesRegex(coverage.CoverageError, "dependency check profile"):
            self.emit()

    def test_rejects_undeclared_postgresql_target(self):
        self.receipt["postgresql_version"] = "15.19"
        with self.assertRaisesRegex(coverage.CoverageError, "absent from declared support"):
            self.emit()

    def test_rejects_tested_version_outside_archive_range(self):
        self.extension_name = (
            "postgis_tiger_geocoder-2025.2-postgresql-16.15-to-17.11-"
            "linux-x86_64.tar.gz")
        self.receipt["extension_archive"] = self.extension_name
        self.metadata["postgresql_version"] = "17.11"
        self.receipt["archives"] = {}
        self._write_extension()
        self._write_checksums()
        with self.assertRaisesRegex(coverage.CoverageError, "outside the extension archive range"):
            self.emit()

    def test_creates_receipt_from_ci_step_results(self):
        steps = self.root / "step-results.json"
        steps.write_text(json.dumps({"archive-assembly": "success",
                                     "tiger-normalize": "success"}))
        environment = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "987",
                       "GITHUB_REPOSITORY": "o/r", "GITHUB_SERVER_URL": "https://github.com"}
        receipt_creator.create(
            self.root, self.archives, self.core_archives, self.receipt_path,
            self.profile_id, "PostGIS TIGER Geocoder", "2025.2", "18.6", "18.6",
            "x86_64", "minimum", "5.15.0-1109-kvm", "Ubuntu 22.04.5 LTS",
            "22.04", "sha256:" + "b" * 64, "success", True, steps, environment)
        receipt = json.loads(self.receipt_path.read_text())
        self.assertEqual(receipt["case_results"], self.receipt["case_results"])
        self.assertEqual(receipt["archives"], self.receipt["archives"])
        self.assertEqual(len(emitter.emit(self.root, self.archives, self.core_archives,
                                          self.receipt_path, self.output)), 1)

    def test_receipt_creator_requires_complete_steps(self):
        steps = self.root / "step-results.json"
        steps.write_text(json.dumps({"archive-assembly": "success"}))
        environment = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "987",
                       "GITHUB_REPOSITORY": "o/r", "GITHUB_SERVER_URL": "https://github.com"}
        with self.assertRaisesRegex(coverage.CoverageError, "exactly every registered"):
            receipt_creator.create(
                self.root, self.archives, self.core_archives, self.receipt_path,
                self.profile_id, "PostGIS TIGER Geocoder", "2025.2", "18.6", "18.6",
                "x86_64", "minimum", "5.15.0-1109-kvm", "Ubuntu 22.04.5 LTS",
                "22.04", "sha256:" + "b" * 64, "success", True, steps, environment)


if __name__ == "__main__":
    unittest.main()
