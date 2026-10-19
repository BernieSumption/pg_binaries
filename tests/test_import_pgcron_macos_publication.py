"""Tests for importing pg_cron macOS publication evidence."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_emit_pgcron_macos_publication import PgCronMacOSFixture
import import_pgcron_macos_publication as importer


class ImportPgCronMacOSPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PgCronMacOSFixture()
        self.addCleanup(self.fixture.close)

    def import_fixture(self, fixture):
        return importer.import_run(
            fixture.root, fixture.core, fixture.output, "12345678901",
            target_config=fixture.target_config,
        )

    def test_import_retains_receipt_record_and_reports(self):
        self.fixture.emit()
        retained = self.import_fixture(self.fixture)
        self.assertTrue(any(path.endswith("current-receipt.json") for path in retained))
        self.assertTrue(any(path.startswith("support/verification/") for path in retained))
        evidence = (self.fixture.root / "support/evidence/pgcron-macos-publication-"
                    f"12345678901/{self.fixture.architecture}")
        self.assertTrue((evidence / "attempt.json").is_file())
        self.assertTrue((evidence / "static-analysis.json").is_file())
        self.assertTrue((evidence / "pg-cron-macho-inspection.json").is_file())
        self.assertTrue((evidence / "probe-output.txt").is_file())

    def test_imports_both_macos_architectures(self):
        for architecture in ("arm64", "x86_64"):
            with self.subTest(architecture=architecture):
                fixture = PgCronMacOSFixture(architecture)
                try:
                    fixture.emit()
                    retained = self.import_fixture(fixture)
                    self.assertTrue(any(path.startswith("support/verification/")
                                        for path in retained))
                    self.assertTrue((fixture.root / "support/evidence/pgcron-macos-publication-"
                                     f"12345678901/{architecture}/attempt.json").is_file())
                finally:
                    fixture.close()

    def test_imports_pgxs_so_module_with_matching_report(self):
        fixture = PgCronMacOSFixture(module_extension="so")
        try:
            fixture.emit()
            retained = self.import_fixture(fixture)
            self.assertTrue(any(path.startswith("support/verification/")
                                for path in retained))
        finally:
            fixture.close()

    def test_requires_target_config(self):
        with self.assertRaises(TypeError):
            importer.import_run(self.fixture.root, self.fixture.core,
                                self.fixture.output, "12345678901")

    def test_import_rejects_unresolved_target(self):
        value = json.loads(self.fixture.target_config.read_text())
        value["core_archive"] = {"basename": self.fixture.core_name}
        self.fixture.target_config.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "not been resolved"):
            self.import_fixture(self.fixture)

    def test_import_rejects_changed_final_extension_bytes(self):
        self.fixture.emit()
        self.fixture.extension.write_bytes(self.fixture.extension.read_bytes() + b"tamper")
        with self.assertRaisesRegex(Exception, "checksum sidecar"):
            self.import_fixture(self.fixture)

    def test_import_rejects_core_bytes_outside_resolved_identity(self):
        self.fixture.emit()
        self.fixture.core_archive.write_bytes(b"tampered core")
        self.fixture._sidecar(self.fixture.core_archive)
        with self.assertRaisesRegex(Exception, "checksum differs from the resolved target"):
            self.import_fixture(self.fixture)

    def test_import_rejects_oversized_raw_attempt(self):
        self.fixture.emit()
        attempt = self.fixture.output / "publication/attempt.json"
        attempt.write_bytes(b" " * (importer.MAX_EVIDENCE_BYTES + 1))
        with self.assertRaisesRegex(Exception, "regular file of at most"):
            self.import_fixture(self.fixture)

    def test_import_retains_incomplete_raw_attempt(self):
        self.fixture.extension.unlink()
        self.fixture.emit({"archive-suite": "failure", "static-analysis": "skipped"})
        retained = self.import_fixture(self.fixture)
        self.assertTrue(any(path.endswith("attempt.json") for path in retained))
        self.assertFalse((self.fixture.root / "support/verification").exists())

    def test_import_rejects_changed_retained_probe_report(self):
        self.fixture.emit()
        probe = self.fixture.output / "probe-output.txt"
        probe.write_text(probe.read_text().replace("scheduled_job_rows=1",
                                                   "scheduled_job_rows=0"))
        with self.assertRaisesRegex(Exception, "receipt digest differs"):
            self.import_fixture(self.fixture)

    def test_import_does_not_replace_prior_evidence_with_different_bytes(self):
        self.fixture.emit()
        evidence = (self.fixture.root / "support/evidence/pgcron-macos-publication-"
                    f"12345678901/{self.fixture.architecture}/attempt.json")
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("different evidence\n")
        with self.assertRaisesRegex(Exception, "refusing to replace retained evidence"):
            self.import_fixture(self.fixture)


if __name__ == "__main__":
    unittest.main()
