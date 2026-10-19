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
        self.status.write_text("core\trunning\ncore\tpassed\ndiagnostics\trunning\ndiagnostics\tpassed\n")
        self.assertEqual(phases.read_outcomes(self.status), {"core": "success", "diagnostics": "success"})

    def test_failed_phase_is_preserved(self):
        self.status.write_text("core\trunning\ncore\tpassed\ndiagnostics\trunning\ndiagnostics\tfailed(7)\n")
        self.assertEqual(phases.read_outcomes(self.status), {"core": "success", "diagnostics": "failure"})

    def test_missing_duplicate_and_running_rows_fail_closed(self):
        self.status.write_text("core\trunning\ncore\tpassed\ncore\tpassed\ndiagnostics\trunning\n")
        self.assertEqual(phases.read_outcomes(self.status), {"core": "failure", "diagnostics": "failure"})

    def test_missing_or_corrupt_status_fails_closed(self):
        self.assertTrue(all(value == "failure" for value in phases.read_outcomes(self.status).values()))
        self.status.write_text("core\trunning\ncore\tpassed\ndiagnostics\trunning\ndiagnostics\tpassed\nextra\tpassed\n")
        self.assertTrue(all(value == "failure" for value in phases.read_outcomes(self.status).values()))

    def test_explicit_skipped_invocation_does_not_require_status_file(self):
        self.assertEqual(phases.read_outcomes(self.status, verification_skipped=True), {
            phase: "skipped" for phase in phases.PHASES
        })

    def test_cli_emits_compact_receipt_writer_json(self):
        self.status.write_text("core\trunning\ncore\tpassed\ndiagnostics\trunning\ndiagnostics\tpassed\n")
        result = subprocess.run([sys.executable, str(Path(phases.__file__)), "--status", str(self.status)],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), {"core": "success", "diagnostics": "success"})
        self.assertNotIn(" ", result.stdout)


if __name__ == "__main__":
    unittest.main()
