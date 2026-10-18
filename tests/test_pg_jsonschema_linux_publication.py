"""Focused checks for Linux pg_jsonschema candidate evidence helpers."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import emit_pg_jsonschema_linux_publication as publication
import import_pg_jsonschema_linux_publication as importer
import coverage


class LinuxPublicationHelpers(unittest.TestCase):
    def test_architecture_profiles_are_scoped(self):
        self.assertEqual(set(publication.PROFILE_IDS), {"x86_64", "arm64"})
        self.assertNotEqual(publication.PROFILE_IDS["x86_64"], publication.PROFILE_IDS["arm64"])

    def test_step_outcomes_are_mapped(self):
        self.assertEqual(publication._step("success"), "passed")
        self.assertEqual(publication._step("failure"), "failed")
        self.assertEqual(publication._step("cancelled"), "skipped")
        with self.assertRaises(coverage.CoverageError):
            publication._step("unexpected")

    def test_verify_failure_marks_sql_skipped_when_elf_check_failed(self):
        self.assertEqual(publication._case_results("failure", "failed"), ("skipped", "failure"))
        self.assertEqual(publication._case_results("failure", "passed"), ("failure", "success"))
        self.assertEqual(publication._case_results("success", "passed"), ("success", "success"))

    def test_failed_build_still_emits_iterable_raw_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            archives = Path(directory) / "archives"
            core_dir = Path(directory) / "core"
            output = archives / "publication"
            archives.mkdir()
            core_dir.mkdir()
            profile = {"profile_revision": "b" * 64, "case_ids": list(publication.CASES)}
            with patch.object(coverage, "verification_profile", return_value=profile):
                paths = publication.emit(ROOT, archives, core_dir, output, "arm64", "failure", "skipped",
                                         "c" * 40, "12345", "owner/repo", "https://github.com", "image")
            self.assertEqual(paths, (output / "attempt.json",))
            attempt = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertEqual(attempt["workflow_steps"], {"build": "failure", "verify": "skipped"})
            self.assertEqual(attempt["steps"], {"archive-suite": "skipped", "elf-closure": "skipped"})

    def test_sidecar_binds_exact_archive_name_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "candidate.tar.gz"
            archive.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()
            Path(str(archive) + ".sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
            publication._sidecar(archive, digest)
            Path(str(archive) + ".sha256").write_text(f"{digest}  other.tar.gz\n", encoding="utf-8")
            with self.assertRaises(coverage.CoverageError):
                publication._sidecar(archive, digest)

    def test_emit_binds_report_to_final_archive_and_keeps_release_ineligible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = ROOT
            archives = Path(directory) / "archives"
            core_dir = Path(directory) / "core"
            output = archives / "publication"
            archives.mkdir()
            core_dir.mkdir()
            arch = "x86_64"
            archive_name = "pg_jsonschema-0.3.4-postgresql-18.6-linux-x86_64.tar.gz"
            core_name = "postgresql-18.6-linux-x86_64.tar.gz"
            archive, core = archives / archive_name, core_dir / core_name
            archive.write_bytes(b"final candidate archive")
            core.write_bytes(b"pinned core archive")
            archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            core_hash = hashlib.sha256(core.read_bytes()).hexdigest()
            for path in (archive, core):
                Path(str(path) + ".sha256").write_text(
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n", encoding="utf-8")
            static_dir = archives / "static-analysis"
            static_dir.mkdir()
            (static_dir / "pg_jsonschema.json").write_text(json.dumps({
                "outcome": "passed", "architecture": arch,
                "archives": [{"basename": archive_name, "sha256": archive_hash}],
            }), encoding="utf-8")
            (archives / "build-evidence.txt").write_text(
                f"pg_jsonschema_source_commit={publication.SOURCE_COMMIT}\n"
                f"cargo_lock_sha256={publication.CARGO_LOCK_SHA256}\n",
                encoding="utf-8")
            (archives / "cargo-license-inventory.json").write_text("{}\n", encoding="utf-8")
            (archives / "probe-output.txt").write_text(
                "PASS: pg_jsonschema 0.3.4 on relocated PostgreSQL 18.6 in Alpine 3.22\n", encoding="utf-8")
            profile = {"profile_revision": "b" * 64, "case_ids": list(publication.CASES)}
            with patch.object(publication, "CORE_SHA256", {arch: core_hash}), \
                    patch.object(coverage, "verification_profile", return_value=profile), \
                    patch.object(coverage, "validate_verification_record", return_value=True):
                paths = publication.emit(root, archives, core_dir, output, arch, "success", "success",
                                         "c" * 40, "12345", "owner/repo", "https://github.com",
                                         "sha256:" + "d" * 64)
            attempt = json.loads((output / "attempt.json").read_text(encoding="utf-8"))
            record = json.loads((output / "verification-record.json").read_text(encoding="utf-8"))
            self.assertEqual(paths, (output / "attempt.json", output / "current-receipt.json",
                                     output / "verification-record.json"))
            self.assertEqual(attempt["archives"][archive_name], archive_hash)
            self.assertEqual(record["assembled_core"]["sha256"], core_hash)
            self.assertEqual(record["release_eligible"], False)
            self.assertEqual(record["case_results"], {"archive-suite": "passed", "elf-closure": "passed"})
            receipt = json.loads((output / "current-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["archives"][archive_name], archive_hash)
            self.assertEqual(receipt["archives"][core_name], core_hash)
            temporary_root = Path(directory) / "root"
            (temporary_root / "support").mkdir(parents=True)
            (temporary_root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
            with patch.object(publication, "CORE_SHA256", {arch: core_hash}), \
                    patch.object(coverage, "verification_profile", return_value=profile), \
                    patch.object(coverage, "validate_verification_record", return_value=True):
                retained = importer.import_run(temporary_root, core_dir, archives, "12345")
            self.assertTrue(any(name.endswith("/attempt.json") for name in retained))
            self.assertTrue(any(name.endswith("/verification-record.json") for name in retained))
            self.assertTrue((temporary_root / "support/verification/pg_jsonschema-0.3.4-postgresql-18.6-linux-x86_64-current-12345.json").is_file())
            self.assertTrue(any(name.endswith("/pg_jsonschema-0.3.4-postgresql-18.6-linux-x86_64.tar.gz.sha256")
                                for name in retained))
            original_archive = archive.read_bytes()
            archive.write_bytes(b"tampered final archive")
            with patch.object(publication, "CORE_SHA256", {arch: core_hash}), \
                    patch.object(coverage, "verification_profile", return_value=profile), \
                    patch.object(coverage, "validate_verification_record", return_value=True), \
                    self.assertRaises(coverage.CoverageError):
                importer.import_run(temporary_root, core_dir, archives, "12345")
            archive.write_bytes(original_archive)
            receipt_path = output / "current-receipt.json"
            original_receipt = receipt_path.read_bytes()
            receipt = json.loads(original_receipt)
            receipt["archives"][archive_name] = "0" * 64
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            with patch.object(publication, "CORE_SHA256", {arch: core_hash}), \
                    patch.object(coverage, "verification_profile", return_value=profile), \
                    patch.object(coverage, "validate_verification_record", return_value=True), \
                    self.assertRaises(coverage.CoverageError):
                importer.import_run(temporary_root, core_dir, archives, "12345")
            receipt_path.write_bytes(original_receipt)


if __name__ == "__main__":
    unittest.main()
