"""Focused checks for Linux Address Standardizer candidate evidence."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import coverage
import emit_address_standardizer_linux_publication as publication
import import_address_standardizer_linux_publication as importer


class AddressStandardizerLinuxPublication(unittest.TestCase):
    def setUp(self):
        self.profile = {"profile_revision": "a" * 64,
                        "case_ids": ["archive-suite", "elf-closure"]}

    def test_profiles_are_architecture_specific_and_version_bounded(self):
        self.assertEqual(publication.profile_id("x86_64"),
                         "address-standardizer-publication-linux-x86_64-18.6")
        self.assertNotEqual(publication.profile_id("x86_64"), publication.profile_id("arm64"))
        with self.assertRaises(coverage.CoverageError):
            publication.profile_id("aarch64")

    def test_case_results_preserve_failed_and_skipped_work(self):
        self.assertEqual(publication._case_results("success", "passed"),
                         {"archive-suite": "passed", "elf-closure": "passed"})
        self.assertEqual(publication._case_results("failure", "failed"),
                         {"archive-suite": "skipped", "elf-closure": "failed"})
        self.assertEqual(publication._case_results("failure", "passed"),
                         {"archive-suite": "failed", "elf-closure": "passed"})

    def test_emit_and_import_bind_candidate_to_both_archive_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            (root / "support").mkdir(parents=True)
            (root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
            archives, core_dir = Path(temporary) / "archives", Path(temporary) / "core"
            archives.mkdir()
            core_dir.mkdir()
            architecture = "x86_64"
            archive_name = f"address-standardizer-{publication.VERSION}-postgresql-18.6-linux-{architecture}.tar.gz"
            core_name = f"postgresql-18.6-linux-{architecture}.tar.gz"
            archive, core = archives / archive_name, core_dir / core_name
            archive.write_bytes(b"candidate archive containing both SQL extensions")
            core.write_bytes(b"exact pinned core archive")
            archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            core_hash = hashlib.sha256(core.read_bytes()).hexdigest()
            for path, checksum in ((archive, archive_hash), (core, core_hash)):
                Path(str(path) + ".sha256").write_text(f"{checksum}  {path.name}\n", encoding="utf-8")
            static = archives / "static-analysis"
            static.mkdir()
            (static / "address-standardizer.json").write_text(json.dumps({
                "outcome": "passed", "architecture": architecture,
                "archives": [{"basename": core_name, "sha256": core_hash},
                             {"basename": archive_name, "sha256": archive_hash}],
            }), encoding="utf-8")
            (archives / "build-evidence.txt").write_text(
                f"address_standardizer_source_commit={publication.SOURCE_COMMIT}\n"
                f"pcre2_source_sha256={publication.PCRE2_SHA256}\n", encoding="utf-8")
            (archives / "Address-Standardizer-COPYING.txt").write_text("upstream extension licence\n", encoding="utf-8")
            (archives / "PCRE2-COPYING.txt").write_text("upstream PCRE2 licence\n", encoding="utf-8")
            (archives / "probe-output.txt").write_text(
                "PASS: Address Standardizer 3.7.0 with PostgreSQL 18.6 on relocated Alpine 3.22\n", encoding="utf-8")
            output = archives / "publication"
            args = (ROOT, archives, core_dir, output, architecture, "success", "success",
                    "c" * 40, "12345", "owner/repo", "https://github.com",
                    "sha256:" + "d" * 64, "6.17.0-azure")
            with patch.object(publication, "CORE_SHA256", {architecture: core_hash}), \
                    patch.object(coverage, "verification_profile", return_value=self.profile), \
                    patch.object(coverage, "validate_verification_record", return_value=True):
                emitted = publication.emit(*args)
                attempt = json.loads((output / "attempt.json").read_text(encoding="utf-8"))
                receipt = json.loads((output / "current-receipt.json").read_text(encoding="utf-8"))
                record = json.loads((output / "verification-record.json").read_text(encoding="utf-8"))
                retained = importer.import_run(root, core_dir, archives, "12345")

            self.assertEqual(emitted, (output / "attempt.json", output / "current-receipt.json",
                                       output / "verification-record.json"))
            self.assertEqual(attempt["archives"], {archive_name: archive_hash, core_name: core_hash})
            self.assertEqual(receipt["release_eligible"], False)
            self.assertEqual(receipt["redistribution_status"], publication.BLOCK)
            self.assertEqual(record["component"], "address_standardizer")
            self.assertEqual(record["assembled_core"]["sha256"], core_hash)
            self.assertEqual(record["case_results"], {"archive-suite": "passed", "elf-closure": "passed"})
            self.assertTrue(any(name.endswith("/verification-record.json") for name in retained))
            installed = root / "support/verification/address-standardizer-3.7.0-postgresql-18.6-linux-x86_64-current-12345.json"
            self.assertTrue(installed.is_file())

    def test_import_rejects_core_bytes_that_differ_from_pinned_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "support").mkdir()
            (root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
            archives, core = root / "archives", root / "core"
            archives.mkdir()
            core.mkdir()
            (archives / "publication").mkdir()
            attempt = {"schema_version": 1, "run_id": "567", "source_revision": "c" * 40,
                       "profile_id": publication.profile_id("arm64"), "postgresql_version": "18.6",
                       "version": publication.VERSION, "architecture": "arm64", "core_run_id": publication.CORE_RUN,
                       "steps": {"archive-suite": "skipped", "elf-closure": "skipped"},
                       "workflow_steps": {"build": "failure", "verify": "skipped"},
                       "release_eligible": False, "redistribution_status": publication.BLOCK,
                       "archives_present": {"postgresql-18.6-linux-arm64.tar.gz": True,
                                            "address-standardizer-3.7.0-postgresql-18.6-linux-arm64.tar.gz": False},
                       "reports": {}}
            (archives / "publication/attempt.json").write_text(json.dumps(attempt), encoding="utf-8")
            (core / "postgresql-18.6-linux-arm64.tar.gz").write_bytes(b"wrong core bytes")
            (core / "postgresql-18.6-linux-arm64.tar.gz.sha256").write_text(
                hashlib.sha256(b"wrong core bytes").hexdigest() + "  postgresql-18.6-linux-arm64.tar.gz\n",
                encoding="utf-8")
            archive_name = "address-standardizer-3.7.0-postgresql-18.6-linux-arm64.tar.gz"
            (archives / archive_name).write_bytes(b"candidate")
            attempt["archives_present"][archive_name] = True
            (archives / "publication/attempt.json").write_text(json.dumps(attempt), encoding="utf-8")
            with patch.object(coverage, "verification_profile", return_value=self.profile), \
                    patch.object(publication, "CORE_SHA256", {"arm64": "0" * 64}), \
                    self.assertRaises(coverage.CoverageError):
                importer.import_run(root, core, archives, "567")


if __name__ == "__main__":
    unittest.main()
