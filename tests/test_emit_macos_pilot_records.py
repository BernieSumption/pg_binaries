import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import emit_macos_pilot_records as records


class EmitMacOSPilotRecordsTests(unittest.TestCase):
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
            "profiles": {
                "macos-pilot-x86_64": {
                    "scope": "pilot-smoke", "platforms": ["macos-x86_64"],
                    "case_ids": ["core-schema-smoke"], "sources": ["workflow.yml"],
                },
                "macos-pilot-arm64": {
                    "scope": "pilot-smoke", "platforms": ["macos-arm64"],
                    "case_ids": ["core-schema-smoke"], "sources": ["workflow.yml"],
                },
            },
        }), encoding="utf-8")
        (self.root / "support.json").write_text(json.dumps({
            "os_support": {"macos": {"minimum_version": "11.0"}},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"], "linux": ["x86_64", "arm64"]},
        }), encoding="utf-8")
        self.archives = self.root / "archives"
        self.archives.mkdir()
        for name in (
            "postgresql-18.6-macos-x86_64.tar.gz",
            "pgvector-0.8.7-postgresql-18.6-macos-x86_64.tar.gz",
        ):
            data = ("archive " + name).encode()
            (self.archives / name).write_bytes(data)
            checksum = hashlib.sha256(data).hexdigest()
            (self.archives / f"{name}.sha256").write_text(
                f"{checksum}  {name}\n", encoding="utf-8")
        self.static_report = self.root / "static-analysis.json"
        self.write_static_report()
        self.output = self.root / "records"

    def write_static_report(self, architecture="x86_64", **updates):
        report = {
            "passed": True, "architecture": architecture,
            "inspected_files": [{"file": "bin/postgres"}],
            "archives": [{"basename": path.name,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                         for path in sorted(self.archives.glob(f"*macos-{architecture}.tar.gz"))],
        }
        report.update(updates)
        self.static_report.write_text(json.dumps(report), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def emit(self, architecture="x86_64", **kwargs):
        return records.emit(self.root, self.archives, self.output, "18.6", "a" * 40,
                            "15.7", architecture,
                            "macos-15-intel/ImageVersion=2026.01" if architecture == "x86_64"
                            else "macos-15/ImageVersion=2026.01",
                            static_report=self.static_report, **kwargs)

    def test_emits_two_bound_pilot_records(self):
        paths = self.emit()
        self.assertEqual({path.name for path in paths}, {
            "postgresql-18.6-macos-x86_64-12345.json",
            "vector-18.6-macos-x86_64-12345.json",
        })
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], 2)
            self.assertEqual(data["scope"], "pilot-smoke")
            self.assertEqual(data["profile_id"], "macos-pilot-x86_64")
            self.assertEqual(data["test_cases"], ["core-schema-smoke"])
            self.assertEqual(data["verification_profile"]["platforms"], ["macos-x86_64"])
            self.assertEqual(data["verification_profile"]["profile_revision"],
                             data["profile_revision"])
            self.assertEqual(data["test_revision"], "a" * 40)
            self.assertEqual(data["ci"]["source_revision"], "a" * 40)
            self.assertEqual(data["ci"]["build_revision"], "a" * 40)
            self.assertEqual(data["ci"]["test_revision"], "a" * 40)
            self.assertEqual(data["ci"]["run_id"], "12345")
            self.assertEqual(data["platform"], "macos-x86_64")
            self.assertEqual(data["environment"]["os_version"], "15.7")
            self.assertEqual(data["environment"]["image_id"],
                             "macos-15-intel/ImageVersion=2026.01")
            self.assertEqual(data["environment"]["dependency_check_profile"],
                             "macho-system-dependencies-v1")
            self.assertTrue(data["environment"]["dependency_checks_passed"])

    def test_rejects_non_pilot_profile(self):
        path = self.root / "support/verification-profiles.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        registry["profiles"]["macos-pilot-x86_64"]["scope"] = "publication"
        path.write_text(json.dumps(registry), encoding="utf-8")
        with self.assertRaisesRegex(records.coverage.CoverageError,
                                    "not the expected macOS pilot"):
            self.emit()

    def test_emits_arm64_records(self):
        names = (
            "postgresql-18.6-macos-arm64.tar.gz",
            "pgvector-0.8.7-postgresql-18.6-macos-arm64.tar.gz",
        )
        for name in names:
            data = ("archive " + name).encode()
            (self.archives / name).write_bytes(data)
            (self.archives / f"{name}.sha256").write_text(
                f"{hashlib.sha256(data).hexdigest()}  {name}\n", encoding="utf-8")
        self.write_static_report("arm64")
        paths = self.emit(architecture="arm64")
        self.assertEqual({path.name for path in paths}, {
            "postgresql-18.6-macos-arm64-12345.json",
            "vector-18.6-macos-arm64-12345.json",
        })
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["profile_id"], "macos-pilot-arm64")
            self.assertEqual(data["platform"], "macos-arm64")
            self.assertEqual(data["environment"]["architecture"], "arm64")

    def test_rejects_archive_bytes_that_do_not_match_checksum(self):
        (self.archives / "postgresql-18.6-macos-x86_64.tar.gz").write_bytes(b"changed")
        with self.assertRaisesRegex(records.coverage.CoverageError, "checksum does not match"):
            self.emit()

    def test_does_not_leave_partial_records_when_second_archive_fails(self):
        (self.archives / "pgvector-0.8.7-postgresql-18.6-macos-x86_64.tar.gz").write_bytes(b"changed")
        with self.assertRaisesRegex(records.coverage.CoverageError, "checksum does not match"):
            self.emit()
        self.assertFalse(self.output.exists())

    def test_emits_failed_or_skipped_records_with_actual_dependency_result(self):
        for outcome, dependency_result in (("failed", False), ("skipped", True)):
            with self.subTest(outcome=outcome):
                paths = records.emit(
                    self.root, self.archives, self.output, "18.6", "a" * 40,
                    "15.7", "x86_64", "macos-15-intel/ImageVersion=2026.01",
                    outcome, dependency_result,
                )
                for path in paths:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(record["outcome"], outcome)
                    self.assertEqual(record["environment"]["dependency_checks_passed"],
                                     dependency_result)
                    archive = self.archives / (
                        "postgresql-18.6-macos-x86_64.tar.gz"
                        if record["component"] == "postgresql"
                        else "pgvector-0.8.7-postgresql-18.6-macos-x86_64.tar.gz")
                    self.assertEqual(record["sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
                for path in paths:
                    path.unlink()

    def test_rejects_invalid_outcome_and_dependency_status(self):
        with self.assertRaisesRegex(records.coverage.CoverageError, "outcome must be"):
            self.emit(outcome="unknown")
        with self.assertRaisesRegex(records.coverage.CoverageError, "dependency check result"):
            self.emit(dependency_checks_passed="false")

    def test_passed_records_require_valid_static_report(self):
        self.static_report.unlink()
        with self.assertRaisesRegex(records.coverage.CoverageError, "report is required"):
            self.emit()
        self.write_static_report(architecture="arm64")
        with self.assertRaisesRegex(records.coverage.CoverageError, "architecture"):
            self.emit()
        self.write_static_report(inspected_files=[])
        with self.assertRaisesRegex(records.coverage.CoverageError, "inspected_files"):
            self.emit()
        self.write_static_report(archives=[])
        with self.assertRaisesRegex(records.coverage.CoverageError, "archives do not match"):
            self.emit()

    def test_failed_or_skipped_records_do_not_require_static_report(self):
        self.static_report.unlink()
        for outcome in ("failed", "skipped"):
            paths = records.emit(self.root, self.archives, self.output, "18.6", "a" * 40,
                                 "15.7", "x86_64", "macos-15-intel/ImageVersion=2026.01",
                                 outcome, False)
            self.assertEqual(len(paths), 2)
            for path in paths:
                path.unlink()


if __name__ == "__main__":
    unittest.main()
