"""Tests for importing pg_cron macOS arm64 publication evidence."""

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

    def test_import_retains_receipt_record_and_reports(self):
        self.fixture.emit()
        retained = importer.import_run(self.fixture.root, self.fixture.core,
                                       self.fixture.output, "12345678901")
        self.assertTrue(any(path.endswith("current-receipt.json") for path in retained))
        self.assertTrue(any(path.startswith("support/verification/") for path in retained))
        evidence = (self.fixture.root / "support/evidence/pgcron-macos-publication-"
                    "12345678901/arm64")
        self.assertTrue((evidence / "attempt.json").is_file())
        self.assertTrue((evidence / "static-analysis.json").is_file())
        self.assertTrue((evidence / "pg-cron-macho-inspection.json").is_file())
        self.assertTrue((evidence / "probe-output.txt").is_file())

    def test_import_rejects_changed_final_extension_bytes(self):
        self.fixture.emit()
        self.fixture.extension.write_bytes(self.fixture.extension.read_bytes() + b"tamper")
        with self.assertRaisesRegex(Exception, "checksum sidecar"):
            importer.import_run(self.fixture.root, self.fixture.core,
                                self.fixture.output, "12345678901")

    def test_import_retains_incomplete_raw_attempt(self):
        self.fixture.extension.unlink()
        self.fixture.emit({"archive-suite": "failure", "static-analysis": "skipped"})
        retained = importer.import_run(self.fixture.root, self.fixture.core,
                                       self.fixture.output, "12345678901")
        self.assertTrue(any(path.endswith("attempt.json") for path in retained))
        self.assertFalse((self.fixture.root / "support/verification").exists())

    def test_import_rejects_changed_retained_probe_report(self):
        self.fixture.emit()
        probe = self.fixture.output / "probe-output.txt"
        probe.write_text(probe.read_text().replace("scheduled_job_rows=1",
                                                   "scheduled_job_rows=0"))
        with self.assertRaisesRegex(Exception, "receipt digest differs"):
            importer.import_run(self.fixture.root, self.fixture.core,
                                self.fixture.output, "12345678901")

    def test_import_does_not_replace_prior_evidence_with_different_bytes(self):
        self.fixture.emit()
        evidence = (self.fixture.root / "support/evidence/pgcron-macos-publication-"
                    "12345678901/arm64/attempt.json")
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("different evidence\n")
        with self.assertRaisesRegex(Exception, "refusing to replace retained evidence"):
            importer.import_run(self.fixture.root, self.fixture.core,
                                self.fixture.output, "12345678901")


if __name__ == "__main__":
    unittest.main()
