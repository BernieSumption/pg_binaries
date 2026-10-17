import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import emit_linux_minimum_pilot_records as records


class EmitLinuxMinimumPilotRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.architecture = "x86_64"
        arch = records.ARCHITECTURES[self.architecture]
        self.workflow = self.root / ".github/workflows/linux-qemu-515.yml"
        self.workflow.parent.mkdir(parents=True)
        self.workflow.write_text("workflow\n", encoding="utf-8")
        self.script = self.root / arch["script"]
        self.script.parent.mkdir(parents=True)
        self.script.write_text(f"image_sha256={arch['image_sha256']}\n", encoding="utf-8")
        sources = [".github/workflows/linux-qemu-515.yml", arch["script"]]
        self.profiles = self.root / "support/verification-profiles.json"
        self.profiles.parent.mkdir(parents=True)
        profile_sources = sources + ["tests/test_emit_linux_minimum_pilot_records.py"]
        for source in profile_sources:
            if source not in sources:
                path = self.root / source
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("source\n", encoding="utf-8")
        self.profiles.write_text(json.dumps({"schema_version": 1, "profiles": {
            arch["profile"]: {
                "scope": "pilot-smoke", "platforms": ["linux-x86_64"],
                "case_ids": ["core-schema-smoke"], "sources": sorted(profile_sources),
            },
        }}), encoding="utf-8")
        (self.root / "support.json").write_text(json.dumps({
            "os_support": {"linux": {"minimum_version": "5.15"}},
            "platform_architectures": {"linux": ["x86_64", "arm64"]},
        }), encoding="utf-8")

        self.archives = self.root / "archives"
        self.archives.mkdir()
        self.names = (
            "postgresql-18.6-linux-x86_64.tar.gz",
            "pgvector-0.8.7-postgresql-18.6-linux-x86_64.tar.gz",
        )
        checksums = []
        for name in self.names:
            data = ("archive " + name).encode()
            digest = hashlib.sha256(data).hexdigest()
            (self.archives / name).write_bytes(data)
            (self.archives / f"{name}.sha256").write_text(f"{digest}  {name}\n", encoding="utf-8")
            checksums.append(f"{digest}  /archives/{name}")
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        (self.evidence / "archive-checksums.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
        arch = records.ARCHITECTURES[self.architecture]
        (self.evidence / "environment.txt").write_text(
            f"test_revision={'a' * 40}\npostgresql_version=18.6\nimage_sha256={arch['image_sha256']}\n",
            encoding="utf-8")
        (self.evidence / "full-verifier.log").write_text(
            "guest_os=Ubuntu 22.04.5 LTS\nguest_kernel=5.15.0-1109-kvm\n"
            "server stopped\nPASS: moved PostgreSQL 18.6 archive and pgvector 0.8.7 archive on Ubuntu 22.04.5 LTS\n",
            encoding="utf-8")
        self.output = self.root / "records"
        self.original_env = {key: os.environ.get(key) for key in (
            "GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL")}
        os.environ.update({"GITHUB_RUN_ID": "12345", "GITHUB_REPOSITORY": "owner/repo",
                           "GITHUB_SERVER_URL": "https://github.com"})
        self.addCleanup(self.restore_env)

    def restore_env(self):
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def tearDown(self):
        self.temp.cleanup()

    def emit(self, outcome="passed"):
        return records.emit(self.root, self.archives, self.evidence, self.output,
                            "18.6", self.architecture, "a" * 40, outcome)

    def test_emits_two_minimum_endpoint_records_bound_to_archive_bytes(self):
        paths = self.emit()
        self.assertEqual({path.name for path in paths}, {
            "postgresql-18.6-linux-x86_64-minimum-12345.json",
            "vector-18.6-linux-x86_64-minimum-12345.json",
        })
        for path in paths:
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["schema_version"], 2)
            self.assertEqual(record["scope"], "pilot-smoke")
            self.assertEqual(record["environment"]["endpoint"], "minimum")
            self.assertEqual(record["environment"]["os_version"], "5.15")
            self.assertEqual(record["environment"]["kernel_release"], "5.15.0-1109-kvm")
            self.assertEqual(record["environment"]["image_id"],
                             "sha256:" + records.ARCHITECTURES[self.architecture]["image_sha256"])

    def test_rejects_archive_checksum_disagreement_without_partial_records(self):
        (self.archives / self.names[1]).write_bytes(b"changed")
        with self.assertRaisesRegex(records.coverage.CoverageError, "checksum does not match"):
            self.emit()
        self.assertFalse(self.output.exists())

    def test_rejects_unpinned_guest_image(self):
        path = self.evidence / "environment.txt"
        path.write_text(path.read_text().replace(records.ARCHITECTURES[self.architecture]["image_sha256"], "0" * 64))
        with self.assertRaisesRegex(records.coverage.CoverageError, "pinned guest image"):
            self.emit()

    def test_rejects_non_515_guest_or_failed_log(self):
        path = self.evidence / "full-verifier.log"
        path.write_text(path.read_text().replace("5.15.0-1109-kvm", "6.8.0-1"))
        with self.assertRaisesRegex(records.coverage.CoverageError, "Linux 5.15"):
            self.emit()

    def test_rejects_missing_success_marker(self):
        path = self.evidence / "full-verifier.log"
        path.write_text(path.read_text().replace("PASS:", "FAIL:"))
        with self.assertRaisesRegex(records.coverage.CoverageError, "no successful archive"):
            self.emit()

    def test_failed_and_skipped_outcomes_are_bound_to_existing_archive_bytes(self):
        for outcome in ("failed", "skipped"):
            with self.subTest(outcome=outcome):
                self.output = self.root / outcome
                paths = records.emit(self.root, self.archives, None, self.output,
                                     "18.6", self.architecture, "a" * 40, outcome)
                self.assertEqual(len(paths), 2)
                for path in paths:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(record["outcome"], outcome)
                    self.assertEqual(record["environment"]["dependency_checks_passed"], False)
                    self.assertEqual(record["environment"]["clean_system"], False)
                    self.assertEqual(record["environment"]["image_id"],
                                     "sha256:" + records.ARCHITECTURES[self.architecture]["image_sha256"])
                    self.assertNotIn("kernel_release", record["environment"])

    def test_passed_outcome_requires_success_evidence(self):
        with self.assertRaisesRegex(records.coverage.CoverageError, "requires QEMU evidence"):
            records.emit(self.root, self.archives, None, self.output,
                         "18.6", self.architecture, "a" * 40, "passed")


if __name__ == "__main__":
    unittest.main()
