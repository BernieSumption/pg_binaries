from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.windows_core_pin import (ARTIFACT_PIN_FIELDS, PIN_PATH, MissingArtifactPin,
                                    load_artifact_pin, load_identity)


class WindowsCorePinTests(unittest.TestCase):
    def test_loads_the_shared_core_identity(self):
        identity = load_identity()
        self.assertEqual(identity["build_id"], f"github-{identity['run_id']}-1")
        self.assertEqual(identity["archive_name"], "postgresql-18.6-windows-x86_64.tar.gz")

    def test_each_pin_matches_its_retained_core_archive(self):
        root = PIN_PATH.parents[2]
        for version in ("15.19", "16.15", "17.11", "18.6"):
            with self.subTest(postgresql_version=version):
                identity = load_identity(pg_version=version)
                record = json.loads((root / "support/verification" /
                    f"postgresql-{version}-windows-x86_64-current-{identity['run_id']}.json").read_text())
                self.assertEqual(identity["sha256"], record["sha256"])
                self.assertEqual(identity["source_revision"], record["ci"]["build_revision"])
                self.assertEqual(record["outcome"], "passed")
                with self.assertRaisesRegex(ValueError, "expected"):
                    load_identity(PIN_PATH, pg_version=version if version != "18.6" else "15.19")

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

    def test_loads_valid_exact_artifact_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pin.json"
            pin = {
                "schema_version": 1,
                "workflow": "postgresql-windows-selected-publication.yml",
                "run_id": 12345,
                "artifact_name": "windows-core-selected-18.6-build-12345",
                "archive_name": "postgresql-18.6-windows-x86_64.tar.gz",
                "sha256": "a" * 64,
            }
            path.write_text(json.dumps(pin), encoding="utf-8")
            self.assertEqual(load_artifact_pin("18.6", path), pin)
            self.assertEqual(set(pin), ARTIFACT_PIN_FIELDS)

    def test_missing_artifact_pin_is_distinct_for_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(MissingArtifactPin):
                load_artifact_pin("18.6", Path(temp) / "absent.json")

    def test_rejects_artifact_pin_with_mismatched_run_or_target(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pin.json"
            pin = {
                "schema_version": 1,
                "workflow": "postgresql-windows-selected-publication.yml",
                "run_id": 12345,
                "artifact_name": "windows-core-selected-18.6-build-12345",
                "archive_name": "postgresql-18.6-windows-x86_64.tar.gz",
                "sha256": "a" * 64,
            }
            for key, value in (("run_id", True), ("archive_name", "other.tar.gz"),
                               ("artifact_name", "windows-core-selected-18.6-build-999"),
                               ("sha256", "A" * 64)):
                invalid = dict(pin, **{key: value})
                path.write_text(json.dumps(invalid), encoding="utf-8")
                with self.subTest(key=key), self.assertRaises(ValueError):
                    load_artifact_pin("18.6", path)


if __name__ == "__main__":
    unittest.main()
