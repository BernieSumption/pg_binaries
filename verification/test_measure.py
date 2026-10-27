import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MeasureCommandTests(unittest.TestCase):
    def run_measure(self, output: Path, child_code: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "verification.measure", "--disk-path",
             str(output.parent), str(output), "--", sys.executable, "-c", child_code],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )

    def test_records_successful_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "measure.json"
            completed = self.run_measure(output, "import time; time.sleep(0.2)")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertGreater(record["elapsed_seconds"], 0)
            self.assertGreater(record["baseline_used_bytes"], 0)
            self.assertGreaterEqual(record["peak_added_bytes"], 0)
            self.assertEqual(record["child_exit_code"], 0)

    def test_records_nonzero_child_and_propagates_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "measure.json"
            completed = self.run_measure(output, "raise SystemExit(7)")
            self.assertEqual(completed.returncode, 7)
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(record["child_exit_code"], 7)
            self.assertGreaterEqual(record["peak_added_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
