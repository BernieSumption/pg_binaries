"""Focused checks for the pgTAP PostgreSQL 17.11 macOS profiles."""

from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import emit_pgtap_macos_17_11_publication as arm_emitter
import emit_pgtap_macos_x86_64_17_11_publication as intel_emitter
import emit_pgtap_macos_publication as arm_18_emitter
import emit_pgtap_macos_x86_64_publication as intel_18_emitter
import import_pgtap_macos_17_11_publication as arm_importer
import import_pgtap_macos_x86_64_17_11_publication as intel_importer


class PgTapMacOSPostgreSQL1711Tests(unittest.TestCase):
    def test_core_pins_match_current_postgresql_records(self):
        for emitter in (arm_emitter, intel_emitter):
            record_path = (Path("support/verification") /
                           f"postgresql-17.11-macos-{emitter.ARCHITECTURE}-current-{emitter.PIN['run_id']}.json")
            record = json.loads(record_path.read_text())
            self.assertEqual(record["outcome"], "passed")
            self.assertEqual(record["sha256"], emitter.PIN["sha256"])
            self.assertEqual(record["ci"]["run_id"], emitter.PIN["run_id"])
            self.assertEqual(record["profile_id"], f"macos-publication-current-{emitter.ARCHITECTURE}")
        self.assertEqual(arm_emitter.PROFILE_ID, "pgtap-publication-macos-arm64-17.11")
        self.assertEqual(intel_emitter.PROFILE_ID, "pgtap-publication-macos-x86_64-17.11")
        self.assertEqual(arm_importer.CORE_SHA256, arm_emitter.CORE_SHA256)
        self.assertEqual(intel_importer.CORE_SHA256, intel_emitter.CORE_SHA256)

    def test_17_11_adapters_leave_18_6_emitters_unchanged(self):
        self.assertEqual(arm_emitter.implementation.PG_VERSION, "18.6")
        self.assertEqual(intel_emitter.implementation.PG_VERSION, "18.6")
        self.assertEqual(arm_18_emitter.PG_VERSION, "18.6")
        self.assertEqual(intel_18_emitter.PG_VERSION, "18.6")

    def test_adapters_apply_pins_only_during_emission_and_import(self):
        for emitter, importer in ((arm_emitter, arm_importer), (intel_emitter, intel_importer)):
            with self.subTest(profile=emitter.PROFILE_ID):
                observed = {}

                def capture(*args, **kwargs):
                    observed.update(version=emitter.implementation.PG_VERSION,
                                    profile=emitter.implementation.PROFILE_ID,
                                    checksum=emitter.implementation.CORE_SHA256)
                    return "delegated"

                with patch.object(emitter.implementation, "emit", capture):
                    self.assertEqual(emitter.emit(), "delegated")
                self.assertEqual(observed, {"version": "17.11", "profile": emitter.PROFILE_ID,
                                            "checksum": emitter.CORE_SHA256})
                self.assertEqual(emitter.implementation.PG_VERSION, "18.6")

                observed.clear()
                with patch.object(importer.importer, "import_run", capture):
                    self.assertEqual(importer.import_run(), "delegated")
                self.assertEqual(observed, {"version": "17.11", "profile": importer.PROFILE_ID,
                                            "checksum": importer.CORE_SHA256})
                self.assertEqual(emitter.implementation.PG_VERSION, "18.6")


if __name__ == "__main__":
    unittest.main()
