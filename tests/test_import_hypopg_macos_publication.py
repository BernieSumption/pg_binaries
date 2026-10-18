"""Focused tests for importing HypoPG macOS publication evidence."""

from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_emit_hypopg_macos_publication import HypoPGMacOSFixture
from hypopg_macos_target import load_target_config
import import_hypopg_macos_publication as importer


class ImportHypoPGMacOSPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = HypoPGMacOSFixture()
        self.addCleanup(self.fixture.close)

    def test_import_retains_receipt_record_and_final_archive_reports(self):
        self.fixture.emit()
        retained = self.fixture.import_run()
        self.assertTrue(any(path.endswith("current-receipt.json") for path in retained))
        self.assertTrue(any(path.startswith("support/verification/") for path in retained))
        evidence = (self.fixture.root / "support/evidence/hypopg-macos-publication-"
                    "12345678901/arm64/18.6")
        self.assertTrue((evidence / "attempt.json").is_file())
        self.assertTrue((evidence / "static-analysis.json").is_file())
        self.assertTrue((evidence / "probe-output.txt").is_file())

    def test_import_rejects_changed_final_archive_bytes(self):
        self.fixture.emit()
        self.fixture.extension.write_bytes(self.fixture.extension.read_bytes() + b"tamper")
        with self.assertRaisesRegex(Exception, "checksum sidecar"):
            self.fixture.import_run()

    def test_import_retains_incomplete_raw_attempt(self):
        self.fixture.extension.unlink()
        self.fixture.emit({"archive-suite": "failure", "static-analysis": "skipped"})
        retained = self.fixture.import_run()
        self.assertTrue(any(path.endswith("attempt.json") for path in retained))
        self.assertFalse((self.fixture.root / "support/verification").exists())

    def test_import_refuses_to_replace_conflicting_retained_evidence(self):
        self.fixture.emit()
        destination = (self.fixture.root / "support/evidence/hypopg-macos-publication-"
                       "12345678901/arm64/18.6/attempt.json")
        destination.parent.mkdir(parents=True)
        destination.write_text("existing evidence\n")

        with self.assertRaisesRegex(Exception, "refusing to replace retained evidence"):
            self.fixture.import_run()
        self.assertEqual(destination.read_text(), "existing evidence\n")

    def test_same_run_imports_for_two_postgresql_versions_have_separate_evidence(self):
        root = Path(__file__).resolve().parents[1]
        target_17 = load_target_config(root / "tools/hypopg_macos_pins/17.11-arm64.json")
        target_18 = load_target_config(root / "tools/hypopg_macos_pins/18.6-arm64.json")
        fixture_17 = HypoPGMacOSFixture(target_17)
        fixture_18 = HypoPGMacOSFixture(target_18)
        self.addCleanup(fixture_17.close)
        self.addCleanup(fixture_18.close)

        registry = json.loads((fixture_18.root / "support/verification-profiles.json").read_text())
        for relative in registry["profiles"][target_18.profile_id]["sources"]:
            source = fixture_18.root / relative
            destination = fixture_17.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())

        for fixture in (fixture_17, fixture_18):
            fixture.emit()
        retained_17 = importer.import_run(fixture_17.root, fixture_17.core,
                                          fixture_17.output, "12345678901", fixture_17.target)
        retained_18 = importer.import_run(fixture_17.root, fixture_18.core,
                                          fixture_18.output, "12345678901", fixture_18.target)

        self.assertTrue(any("/arm64/17.11/attempt.json" in path for path in retained_17))
        self.assertTrue(any("/arm64/18.6/attempt.json" in path for path in retained_18))
        self.assertTrue((fixture_17.root / "support/verification"
                         / "hypopg-1.4.3-postgresql-17.11-macos-arm64-current-12345678901.json").is_file())
        self.assertTrue((fixture_17.root / "support/verification"
                         / "hypopg-1.4.3-postgresql-18.6-macos-arm64-current-12345678901.json").is_file())


if __name__ == "__main__":
    unittest.main()
