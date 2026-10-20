import json
import tempfile
import unittest
from pathlib import Path

from tools.macos_core_pin import MissingPin, load_pin


class MacOSCorePinTests(unittest.TestCase):
    def write_pin(self, directory, value):
        path = Path(directory) / "pin.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def valid_pin(self):
        return {
            "schema_version": 1,
            "workflow": "build-postgresql.yml",
            "run_id": 12345,
            "artifact_name": "postgresql-18.6-macos-arm64",
            "archive_name": "postgresql-18.6-macos-arm64.tar.gz",
            "sha256": "a" * 64,
        }

    def test_loads_valid_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_pin(directory, self.valid_pin())
            self.assertEqual(load_pin("18.6", "arm64", path), self.valid_pin())

    def test_missing_pin_is_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(MissingPin):
                load_pin("18.6", "arm64", Path(directory) / "absent.json")

    def test_rejects_malformed_fields_and_values(self):
        with tempfile.TemporaryDirectory() as directory:
            for mutate in (
                lambda pin: pin.update(extra="field"),
                lambda pin: pin.update(run_id=0),
                lambda pin: pin.update(artifact_name="unsafe/name"),
                lambda pin: pin.update(sha256="A" * 64),
            ):
                pin = self.valid_pin()
                mutate(pin)
                with self.subTest(pin=pin):
                    with self.assertRaises(ValueError):
                        load_pin("18.6", "arm64", self.write_pin(directory, pin))

    def test_rejects_requested_target_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            pin = self.valid_pin()
            pin["archive_name"] = "postgresql-18.6-macos-x86_64.tar.gz"
            with self.assertRaisesRegex(ValueError, "requested target"):
                load_pin("18.6", "arm64", self.write_pin(directory, pin))


if __name__ == "__main__":
    unittest.main()
