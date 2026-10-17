import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import read_combined_verification_phases as phases


class CombinedPhaseOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.status = Path(self.temp.name) / "phases.tsv"

    def tearDown(self):
        self.temp.cleanup()

    def test_maps_complete_status_to_github_outcomes(self):
        self.status.write_text(
            "core\trunning\ncore\tpassed\ndiagnostics\trunning\ndiagnostics\tpassed\n"
            "postgis\trunning\npostgis\tpassed\ntiger\trunning\ntiger\tpassed\n")
        self.assertEqual(phases.read_outcomes(self.status), {
            "core": "success", "diagnostics": "success",
            "postgis": "success", "tiger": "success",
        })

    def test_failed_and_skipped_phases_are_preserved(self):
        self.status.write_text(
            "core\trunning\ncore\tpassed\ndiagnostics\trunning\ndiagnostics\tfailed(7)\n"
            "postgis\tskipped\ntiger\trunning\ntiger\tpassed\n")
        self.assertEqual(phases.read_outcomes(self.status), {
            "core": "success", "diagnostics": "failure",
            "postgis": "skipped", "tiger": "success",
        })

    def test_missing_duplicate_and_running_rows_fail_closed(self):
        self.status.write_text(
            "core\trunning\ncore\tpassed\ncore\tpassed\ndiagnostics\trunning\npostgis\tskipped\n")
        self.assertEqual(phases.read_outcomes(self.status), {
            "core": "failure", "diagnostics": "failure",
            "postgis": "skipped", "tiger": "failure",
        })

    def test_missing_or_corrupt_status_fails_closed(self):
        self.assertTrue(all(value == "failure" for value in phases.read_outcomes(self.status).values()))
        self.status.write_text("core\trunning\ncore\tpassed\ndiagnostics\trunning\ndiagnostics\tpassed\npostgis\trunning\npostgis\tpassed\ntiger\trunning\ntiger\tpassed\nextra\tpassed\n")
        self.assertTrue(all(value == "failure" for value in phases.read_outcomes(self.status).values()))

    def test_explicit_skipped_invocation_does_not_require_status_file(self):
        self.assertEqual(phases.read_outcomes(self.status, verification_skipped=True), {
            phase: "skipped" for phase in phases.PHASES
        })

    def test_cli_emits_compact_receipt_writer_json(self):
        self.status.write_text("core\trunning\ncore\tpassed\ndiagnostics\trunning\ndiagnostics\tpassed\npostgis\tskipped\ntiger\tskipped\n")
        result = subprocess.run(
            [sys.executable, str(Path(phases.__file__)), "--status", str(self.status)],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(json.loads(result.stdout), {
            "core": "success", "diagnostics": "success",
            "postgis": "skipped", "tiger": "skipped",
        })
        self.assertNotIn(" ", result.stdout)


if __name__ == "__main__":
    unittest.main()
