import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import emit_linux_pilot_records as records


class EmitLinuxPilotRecordsTests(unittest.TestCase):
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
        source = "workflow.yml"
        (self.root / source).write_text("pilot workflow\n", encoding="utf-8")
        (self.root / "support/verification-profiles.json").write_text(json.dumps({
            "schema_version": 1,
            "profiles": {"linux-pilot-x86_64": {
                "scope": "pilot-smoke", "platforms": ["linux-x86_64"],
                "case_ids": ["core-schema-smoke"], "sources": [source],
            }},
        }), encoding="utf-8")
        (self.root / "support.json").write_text(json.dumps({
            "os_support": {"linux": {"minimum_version": "5.15"}},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"], "linux": ["x86_64", "arm64"]},
        }), encoding="utf-8")
        self.archives = self.root / "archives"
        self.archives.mkdir()
        for name in (
            "postgresql-18.6-linux-x86_64.tar.gz",
            "pgvector-0.8.7-postgresql-18.6-linux-x86_64.tar.gz",
        ):
            data = ("archive " + name).encode()
            (self.archives / name).write_bytes(data)
            checksum = hashlib.sha256(data).hexdigest()
            (self.archives / f"{name}.sha256").write_text(f"{checksum}  {name}\n", encoding="utf-8")
        self.output = self.root / "records"
        self.release = {"VERSION_ID": "24.04", "PRETTY_NAME": "Ubuntu 24.04.3 LTS"}

    def tearDown(self):
        self.temp.cleanup()

    def emit(self):
        return records.emit(
            self.root, self.archives, self.output, "18.6", "x86_64", "a" * 40,
            "sha256:" + "b" * 64, self.release, "x86_64", "6.8.0-1012-azure",
        )

    def test_emits_two_bound_pilot_records(self):
        paths = self.emit()
        self.assertEqual({path.name for path in paths}, {
            "postgresql-18.6-linux-x86_64-12345.json",
            "vector-18.6-linux-x86_64-12345.json",
        })
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], 2)
            self.assertEqual(data["scope"], "pilot-smoke")
            self.assertEqual(data["profile_id"], "linux-pilot-x86_64")
            self.assertEqual(data["test_revision"], "a" * 40)
            self.assertEqual(data["ci"]["build_revision"], data["ci"]["test_revision"])
            self.assertEqual(data["ci"]["run_id"], "12345")
            self.assertEqual(data["environment"]["os_version"], "6.8.0")
            self.assertEqual(data["environment"]["kernel_release"], "6.8.0-1012-azure")
            self.assertEqual(data["environment"]["distribution"], "Ubuntu 24.04.3 LTS")
            self.assertEqual(data["environment"]["dependency_check_profile"], "linux-runtime-v1")
            self.assertTrue(data["environment"]["dependency_checks_passed"])

    def test_rejects_a_registered_publication_profile(self):
        path = self.root / "support/verification-profiles.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        registry["profiles"]["linux-pilot-x86_64"]["scope"] = "publication"
        path.write_text(json.dumps(registry), encoding="utf-8")
        with self.assertRaisesRegex(records.coverage.CoverageError, "not the expected Linux pilot"):
            self.emit()

    def test_rejects_archive_bytes_that_do_not_match_checksum(self):
        (self.archives / "postgresql-18.6-linux-x86_64.tar.gz").write_bytes(b"changed")
        with self.assertRaisesRegex(records.coverage.CoverageError, "checksum does not match"):
            self.emit()

    def test_does_not_leave_a_partial_pass_record(self):
        (self.archives / "pgvector-0.8.7-postgresql-18.6-linux-x86_64.tar.gz").write_bytes(b"changed")
        with self.assertRaisesRegex(records.coverage.CoverageError, "checksum does not match"):
            self.emit()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
