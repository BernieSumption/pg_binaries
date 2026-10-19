import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
import emit_linux_publication_records as emitter


REPO = Path(__file__).resolve().parents[1]


class LinuxPublicationRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "root"
        self.archives = Path(self.temp.name) / "archives"
        self.output = Path(self.temp.name) / "records"
        (self.root / "support").mkdir(parents=True)
        self.archives.mkdir()
        shutil.copy(REPO / "support.json", self.root / "support.json")
        shutil.copy(REPO / "support/postgresql-releases.json", self.root / "support/postgresql-releases.json")
        (self.root / "source.txt").write_text("verifier source v1\n")
        self.profile_id = "linux-publication-x86_64"
        self.profile_data = {"schema_version": 1, "profiles": {self.profile_id: {
            "scope": "publication", "platforms": ["linux-x86_64"],
            "case_ids": ["archive-install", "vector-ddl"], "sources": ["source.txt"]}}}
        self._write_profile()
        self.names = ["postgresql-18.6-linux-x86_64.tar.gz",
                      "pgvector-0.8.7-postgresql-18.6-linux-x86_64.tar.gz"]
        self.receipt = {
            "profile_id": self.profile_id,
            "profile_revision": coverage.verification_profile(self.root, self.profile_id)["profile_revision"],
            "test_revision": "a" * 40,
            "postgresql_version": "18.6", "architecture": "x86_64",
            "os": "linux", "clean_system": True,
            "endpoint": "current", "kernel_release": "6.8.0-40-generic",
            "distribution": "Ubuntu 22.04.5 LTS", "distribution_version": "22.04",
            "image_id": "sha256:" + "b" * 64,
            "dependency_check_profile": emitter.DEPENDENCY_PROFILE,
            "dependency_checks_passed": True,
            "case_results": {"archive-install": "passed", "vector-ddl": "passed"},
            "archives": {},
            "ci": {"provider": "github-actions", "run_id": "987", "run_url": "https://github.com/o/r/actions/runs/987",
                   "source_revision": "a" * 40, "build_revision": "a" * 40, "test_revision": "a" * 40},
        }
        for index, name in enumerate(self.names):
            data = f"archive fixture {index}".encode()
            (self.archives / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.receipt["archives"][name] = digest
            (self.archives / f"{name}.sha256").write_text(f"{digest}  {name}\n")
        self.receipt_path = Path(self.temp.name) / "receipt.json"
        self._write_receipt()

    def tearDown(self):
        self.temp.cleanup()

    def _write_profile(self):
        (self.root / "support" / "verification-profiles.json").write_text(
            json.dumps(self.profile_data))

    def _write_receipt(self):
        self.receipt_path.write_text(json.dumps(self.receipt))

    def test_emits_valid_records_bound_to_both_archives_and_core(self):
        paths = emitter.emit(self.root, self.archives, self.receipt_path, self.output)
        self.assertEqual(len(paths), 2)
        records = [json.loads(path.read_text()) for path in paths]
        self.assertEqual([record["component"] for record in records], ["postgresql", "vector"])
        self.assertEqual([record["sha256"] for record in records],
                         [self.receipt["archives"][name] for name in self.names])
        self.assertEqual(records[1]["assembled_core"]["archive"], self.names[0])
        for record in records:
            self.assertEqual(record["environment"]["os_version"], "6.8.0")
            self.assertEqual(record["environment"]["kernel_release"], "6.8.0-40-generic")
            self.assertTrue(coverage.validate_verification_record(
                record, coverage.load_json(self.root / "support.json"), self.root))
        verification_dir = self.root / "support" / "verification"
        verification_dir.mkdir()
        for path in paths:
            shutil.copy(path, verification_dir / path.name)
        self.assertEqual(len(coverage.verification_records(
            self.root, coverage.load_json(self.root / "support.json"))), 2)

    def test_rejects_missing_or_extra_cases_and_nonpassed_results(self):
        bad_results = ({"archive-install": "passed"},
                       {"archive-install": "passed", "vector-ddl": "passed", "other": "passed"},
                       {"archive-install": "passed", "vector-ddl": "pending"})
        for results in bad_results:
            with self.subTest(results=results):
                self.receipt["case_results"] = results
                self._write_receipt()
                with self.assertRaises(coverage.CoverageError):
                    emitter.emit(self.root, self.archives, self.receipt_path, self.output)

    def test_preserves_compatible_receipt_revision_and_aggregates_failed_or_skipped_cases(self):
        profile = coverage.verification_profile(self.root, self.profile_id)
        self.receipt["profile_revision"] = profile["compatible_profile_revisions"][-1]
        for results, expected, clean, dependencies in (
                ({"archive-install": "failed", "vector-ddl": "passed"}, "failed", True, True),
                ({"archive-install": "skipped", "vector-ddl": "passed"}, "skipped", False, False),
                ({"archive-install": "skipped", "vector-ddl": "failed"}, "failed", False, False)):
            with self.subTest(outcome=expected, results=results):
                self.receipt["case_results"] = results
                self.receipt["clean_system"] = clean
                self.receipt["dependency_checks_passed"] = dependencies
                self._write_receipt()
                paths = emitter.emit(self.root, self.archives, self.receipt_path, self.output)
                for path in paths:
                    record = json.loads(path.read_text())
                    self.assertEqual(record["outcome"], expected)
                    self.assertEqual(record["profile_revision"], self.receipt["profile_revision"])
                    self.assertEqual(record["case_results"], results)
                    self.assertEqual(record["environment"]["clean_system"], clean)
                    self.assertEqual(record["environment"]["dependency_checks_passed"], dependencies)
                    coverage.validate_verification_record(
                        record, coverage.load_json(self.root / "support.json"), self.root)

    def test_rejects_stale_profile_platform_endpoint_and_provenance(self):
        original = dict(self.receipt)
        self.receipt["profile_revision"] = "0" * 64
        self._write_receipt()
        with self.assertRaisesRegex(coverage.CoverageError, "stale"):
            emitter.emit(self.root, self.archives, self.receipt_path, self.output)
        self.receipt = dict(original, architecture="arm64")
        self._write_receipt()
        with self.assertRaises(coverage.CoverageError):
            emitter.emit(self.root, self.archives, self.receipt_path, self.output)
        self.receipt = dict(original, endpoint="minimum", kernel_release="5.15.0-1109-kvm")
        self._write_receipt()
        with self.assertRaisesRegex(coverage.CoverageError, "endpoint must be current"):
            emitter.emit(self.root, self.archives, self.receipt_path, self.output)
        self.receipt = dict(original, kernel_release="5.14.9")
        self._write_receipt()
        with self.assertRaises(coverage.CoverageError):
            emitter.emit(self.root, self.archives, self.receipt_path, self.output)
        self.receipt = dict(original, endpoint="current", kernel_release="5.15.99")
        self._write_receipt()
        with self.assertRaises(coverage.CoverageError):
            emitter.emit(self.root, self.archives, self.receipt_path, self.output)
        self.receipt = dict(original)
        self.receipt["ci"] = {"provider": "github-actions", "run_id": "1", "run_url": "https://github.com/x/y"}
        self._write_receipt()
        with self.assertRaises(coverage.CoverageError):
            emitter.emit(self.root, self.archives, self.receipt_path, self.output)

    def test_rejects_archive_checksum_and_sidecar_mismatches(self):
        original = self.receipt["archives"][self.names[0]]
        self.receipt["archives"][self.names[0]] = "0" * 64
        self._write_receipt()
        with self.assertRaises(coverage.CoverageError):
            emitter.emit(self.root, self.archives, self.receipt_path, self.output)
        self.receipt["archives"][self.names[0]] = original
        (self.archives / f"{self.names[0]}.sha256").write_text(f"{original}  wrong.tar.gz\n")
        self._write_receipt()
        with self.assertRaises(coverage.CoverageError):
            emitter.emit(self.root, self.archives, self.receipt_path, self.output)

    def test_accepts_current_kernel_above_floor(self):
        self.receipt["endpoint"] = "current"
        self.receipt["kernel_release"] = "6.11.0-1018-azure"
        self._write_receipt()
        paths = emitter.emit(self.root, self.archives, self.receipt_path, self.output)
        self.assertEqual(len(paths), 2)
        self.assertEqual(json.loads(paths[0].read_text())["environment"]["os_version"], "6.11.0")

    def test_passed_records_require_sha256_image_identity(self):
        self.receipt["image_id"] = "ubuntu-22.04"
        self._write_receipt()
        with self.assertRaisesRegex(coverage.CoverageError, "image_id sha256"):
            emitter.emit(self.root, self.archives, self.receipt_path, self.output)

    def test_rejects_archive_for_superseded_pgvector_version(self):
        support_path = self.root / "support.json"
        support = json.loads(support_path.read_text())
        support["extensions"]["pgvector"]["versions"]["0.9.0"] = {
            "postgresql_minimum_major": 15}
        support_path.write_text(json.dumps(support))
        with self.assertRaisesRegex(coverage.CoverageError, "canonical PostgreSQL and pgvector"):
            emitter.emit(self.root, self.archives, self.receipt_path, self.output)

    def test_emits_core_only_record_without_pgvector_archive_or_selection(self):
        core_profile = "postgresql-publication-linux-x86_64-18.6"
        self.profile_data["profiles"][core_profile] = {
            "scope": "publication", "platforms": ["linux-x86_64"],
            "case_ids": ["archive-install"], "sources": ["source.txt"]}
        self._write_profile()
        profile = coverage.verification_profile(self.root, core_profile)
        core_name, vector_name = self.names
        (self.archives / vector_name).unlink()
        (self.archives / f"{vector_name}.sha256").unlink()
        self.receipt.update({
            "publication_mode": "core-only", "profile_id": core_profile,
            "profile_revision": profile["profile_revision"],
            "case_results": {"archive-install": "failed"},
            "archives": {core_name: self.receipt["archives"][core_name]},
        })
        self._write_receipt()
        paths = emitter.emit(self.root, self.archives, self.receipt_path, self.output)
        self.assertEqual(len(paths), 1)
        record = json.loads(paths[0].read_text())
        self.assertEqual(record["component"], "postgresql")
        self.assertEqual(record["outcome"], "failed")
        self.assertEqual(record["case_results"], {"archive-install": "failed"})
        self.assertTrue(coverage.validate_verification_record(
            record, coverage.load_json(self.root / "support.json"), self.root))


if __name__ == "__main__":
    unittest.main()
