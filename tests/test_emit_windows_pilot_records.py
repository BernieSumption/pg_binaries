import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import emit_windows_pilot_records as records


class EmitWindowsPilotRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        original_env = {key: os.environ.get(key) for key in (
            "GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL")}
        os.environ.update({"GITHUB_RUN_ID": "12345", "GITHUB_REPOSITORY": "owner/repo",
                           "GITHUB_SERVER_URL": "https://github.com"})

        def restore_env():
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self.addCleanup(restore_env)
        (self.root / "support").mkdir()
        (self.root / "workflow.yml").write_text("pilot workflow\n", encoding="utf-8")
        (self.root / "support/verification-profiles.json").write_text(json.dumps({
            "schema_version": 1,
            "profiles": {"windows-pilot-x86_64": {
                "scope": "pilot-smoke", "platforms": ["windows-x86_64"],
                "case_ids": ["core-schema-smoke"], "sources": ["workflow.yml"],
            }},
        }), encoding="utf-8")
        (self.root / "support.json").write_text(json.dumps({
            "os_support": {"windows": {"minimum_version": "10.0.10240.0"}},
            "architectures": ["x86_64"],
            "platform_architectures": {"windows": ["x86_64"]},
        }), encoding="utf-8")
        self.archives = self.root / "archives"
        self.archives.mkdir()
        for name in (
            "postgresql-18.6-windows-x86_64.tar.gz",
            "pgvector-0.8.7-postgresql-18.6-windows-x86_64.tar.gz",
        ):
            data = ("archive " + name).encode()
            (self.archives / name).write_bytes(data)
            (self.archives / f"{name}.sha256").write_text(
                f"{hashlib.sha256(data).hexdigest()}  {name}\n", encoding="utf-8")
        self.output = self.root / "records"

    def tearDown(self):
        self.temp.cleanup()

    def emit(self):
        return records.emit(self.root, self.archives, self.output, "18.6", "a" * 40,
                            "10.0.20348.2402", "win22/2026.01")

    def test_emits_two_checksum_bound_current_endpoint_records(self):
        paths = self.emit()
        self.assertEqual({path.name for path in paths}, {
            "postgresql-18.6-windows-x86_64-12345.json",
            "vector-18.6-windows-x86_64-12345.json",
        })
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], 2)
            self.assertEqual(data["scope"], "pilot-smoke")
            self.assertEqual(data["profile_id"], "windows-pilot-x86_64")
            self.assertEqual(data["test_cases"], ["core-schema-smoke"])
            self.assertEqual(data["test_revision"], "a" * 40)
            self.assertEqual(data["ci"]["run_id"], "12345")
            self.assertEqual(data["ci"]["run_url"],
                             "https://github.com/owner/repo/actions/runs/12345")
            self.assertEqual(data["platform"], "windows-x86_64")
            self.assertEqual(data["environment"]["os_version"], "10.0.20348.2402")
            self.assertEqual(data["environment"]["endpoint"], "current")
            self.assertTrue(data["environment"]["clean_system"])
            archive = self.archives / ("postgresql-18.6-windows-x86_64.tar.gz" if
                                      data["component"] == "postgresql" else
                                      "pgvector-0.8.7-postgresql-18.6-windows-x86_64.tar.gz")
            self.assertEqual(data["sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_rejects_archive_bytes_that_do_not_match_checksum_without_partial_output(self):
        (self.archives / "postgresql-18.6-windows-x86_64.tar.gz").write_bytes(b"changed")
        with self.assertRaisesRegex(records.coverage.CoverageError, "checksum does not match"):
            self.emit()
        self.assertFalse(self.output.exists())

    def test_rejects_invalid_current_os_version(self):
        with self.assertRaisesRegex(records.coverage.CoverageError, "numeric dotted version"):
            records.emit(self.root, self.archives, self.output, "18.6", "a" * 40,
                         "Server 2022", "win22/2026.01")

    def test_emits_failed_or_skipped_records_with_dependency_status(self):
        for outcome in ("failed", "skipped"):
            with self.subTest(outcome=outcome):
                paths = records.emit(self.root, self.archives, self.output, "18.6", "a" * 40,
                                     "10.0.20348.2402", "win22/2026.01", outcome, False)
                for path in paths:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(data["outcome"], outcome)
                    self.assertFalse(data["environment"]["dependency_checks_passed"])
                for path in paths:
                    path.unlink()

    def test_rejects_passed_records_when_dependency_check_failed(self):
        with self.assertRaisesRegex(records.coverage.CoverageError,
                                    "passed outcome requires successful dependency checks"):
            records.emit(self.root, self.archives, self.output, "18.6", "a" * 40,
                         "10.0.20348.2402", "win22/2026.01", "passed", False)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
