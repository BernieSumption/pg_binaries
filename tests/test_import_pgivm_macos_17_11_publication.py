"""Focused tests for importing pg_ivm macOS publication evidence."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_emit_pgivm_macos_17_11_publication import pg_ivmMacOSFixture
import import_pgivm_macos_17_11_publication as importer


class ImportPgivmMacOSPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = pg_ivmMacOSFixture()
        self.addCleanup(self.fixture.close)

    def test_import_retains_receipt_record_and_final_archive_reports(self):
        self.fixture.emit()
        retained = importer.import_run(self.fixture.root, self.fixture.core,
                                       self.fixture.output, "12345678901")
        self.assertTrue(any(path.endswith("current-receipt.json") for path in retained))
        self.assertTrue(any(path.startswith("support/verification/") for path in retained))
        evidence = (self.fixture.root / "support/evidence/pgivm-macos-publication-"
                    "12345678901/arm64")
        self.assertTrue((evidence / "attempt.json").is_file())
        self.assertTrue((evidence / "static-analysis.json").is_file())
        self.assertTrue((evidence / "probe-output.txt").is_file())

    def test_import_rejects_changed_final_archive_bytes(self):
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

    def test_import_retains_raw_attempt_when_finalizer_fails(self):
        self.fixture.emit()
        publication = self.fixture.output / "publication"
        (publication / "current-receipt.json").unlink()
        for record in (publication / "records").glob("*.json"):
            record.unlink()
        retained = importer.import_run(self.fixture.root, self.fixture.core,
                                       self.fixture.output, "12345678901")
        self.assertTrue(any(path.endswith("attempt.json") for path in retained))
        self.assertFalse(any(path.startswith("support/verification/") for path in retained))


if __name__ == "__main__":
    unittest.main()
