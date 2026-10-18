"""Focused tests for importing pgTAP macOS publication evidence."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_emit_pgtap_macos_x86_64_publication as fixture_module
import import_pgtap_macos_x86_64_publication as importer


class ImportPgTapMacOSX8664PublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.PgTapMacOSX8664PublicationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_import_retains_receipt_record_and_reports(self):
        self.fixture.emit()
        retained = importer.import_run(
            self.fixture.root, self.fixture.core, self.fixture.out, "12345678901")
        self.assertTrue(any(path.endswith("current-receipt.json") for path in retained))
        self.assertTrue(any(path.startswith("support/verification/") for path in retained))
        evidence = self.fixture.root / "support/evidence/pgtap-macos-publication-12345678901/x86_64"
        self.assertTrue((evidence / "attempt.json").is_file())
        self.assertTrue((evidence / "static-analysis.json").is_file())
        self.assertTrue((evidence / "probe-output.txt").is_file())
        self.assertTrue((evidence / "build-log.txt").is_file())

    def test_import_rejects_changed_final_archive_bytes(self):
        self.fixture.emit()
        self.fixture.extension.write_bytes(self.fixture.extension.read_bytes() + b"tamper")
        with self.assertRaisesRegex(Exception, "checksum sidecar"):
            importer.import_run(
                self.fixture.root, self.fixture.core, self.fixture.out, "12345678901")

    def test_import_rejects_changed_static_analysis_report(self):
        self.fixture.emit()
        report = self.fixture.out / "static-analysis.json"
        report.write_text(report.read_text() + " ")
        with self.assertRaisesRegex(Exception, "digest does not match retained static_analysis"):
            importer.import_run(
                self.fixture.root, self.fixture.core, self.fixture.out, "12345678901")

    def test_import_retains_incomplete_raw_attempt(self):
        self.fixture.extension.unlink()
        self.fixture.emit({"archive-suite": "failure", "static-analysis": "skipped"})
        retained = importer.import_run(
            self.fixture.root, self.fixture.core, self.fixture.out, "12345678901")
        self.assertTrue(any(path.endswith("attempt.json") for path in retained))
        self.assertFalse((self.fixture.root / "support/verification").exists())


if __name__ == "__main__":
    unittest.main()
