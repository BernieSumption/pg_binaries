from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.windows_core_pin import PIN_PATH, load_identity


class WindowsCorePinTests(unittest.TestCase):
    def test_loads_the_shared_current_pin(self):
        identity = load_identity()
        self.assertEqual(identity["run_id"], "39119078655")
        self.assertEqual(identity["build_id"], "github-39119078655-1")
        self.assertEqual(identity["archive_name"], "postgresql-18.6-windows-x86_64.tar.gz")

    def test_fails_closed_for_missing_or_incomplete_identity(self):
        with self.assertRaisesRegex(ValueError, "missing or invalid"):
            load_identity(PIN_PATH.parent / "absent.json")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pin.json"
            path.write_text(json.dumps({"run_id": "39089826690"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing or unexpected fields"):
                load_identity(path)

    def test_fails_closed_for_mismatched_build_id(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pin.json"
            value = load_identity()
            value["build_id"] = "github-1-1"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected 18.6 x86-64 shape"):
                load_identity(path)


if __name__ == "__main__":
    unittest.main()
