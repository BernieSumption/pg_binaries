import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import tarfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
import emit_windows_publication_records as emitter


REPO = Path(__file__).resolve().parents[1]


class WindowsPublicationRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "root"
        (self.root / "support").mkdir(parents=True)
        shutil.copy(REPO / "support.json", self.root / "support.json")
        shutil.copy(REPO / "support/postgresql-releases.json", self.root / "support/postgresql-releases.json")
        (self.root / "profile-source.txt").write_text("Windows publication suite\n")
        self.profile_id = emitter.PROFILE_ID
        profile = {"schema_version": 1, "profiles": {self.profile_id: {
            "scope": "publication", "platforms": ["windows-x86_64"],
            "case_ids": ["archive-suite", "diagnostics", "symbols"],
            "sources": ["profile-source.txt"]}}}
        (self.root / "support/verification-profiles.json").write_text(json.dumps(profile))
        self.archives = Path(self.temp.name) / "downloads"
        self.archives.mkdir()
        self.names = ["postgresql-18.6-windows-x86_64.tar.gz",
                      "pgvector-0.8.7-postgresql-18.6-windows-x86_64.tar.gz"]
        self.digests = {}
        metadata = [
            ("postgresql/manifest.json", {"source_revision": "b" * 40, "build_id": "github-1234567-2"}),
            ("metadata.json", {"source_revision": "c" * 40, "build_id": "github-7654321-1"}),
        ]
        for name, (member_name, value) in zip(self.names, metadata):
            data_buffer = io.BytesIO()
            payload = json.dumps(value).encode()
            with tarfile.open(fileobj=data_buffer, mode="w:gz") as archive:
                member = tarfile.TarInfo(member_name)
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            data = data_buffer.getvalue()
            (self.archives / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.digests[name] = digest
            (self.archives / f"{name}.sha256").write_text(f"{digest}  {name}\n")
        self.step_results = Path(self.temp.name) / "steps.json"
        self.write_steps()
        self.static = Path(self.temp.name) / "pe.json"
        self.symbols = Path(self.temp.name) / "symbols.json"
        self.diagnostics = Path(self.temp.name) / "diagnostics.json"
        self.write_reports()
        self.output = Path(self.temp.name) / "records"
        self.old_env = {key: os.environ.get(key) for key in
                        ("GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL")}
        os.environ.update({"GITHUB_RUN_ID": "7654", "GITHUB_REPOSITORY": "owner/repo",
                           "GITHUB_SERVER_URL": "https://github.com"})
        self.addCleanup(self.restore_env)

    def restore_env(self):
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def tearDown(self):
        self.temp.cleanup()

    def write_steps(self, **updates):
        results = {"archive-suite": "passed", "diagnostics": "passed", "symbols": "passed"}
        results.update(updates)
        self.step_results.write_text(json.dumps(results))

    def write_reports(self, static_updates=None, symbol_updates=None, diagnostic_updates=None):
        static = {"outcome": "passed", "platform": "windows", "architecture": "x86_64",
                  "inspected_files": ["bin/postgres.exe"],
                  "archives": [{"basename": name, "sha256": self.digests[name]} for name in self.names]}
        static.update(static_updates or {})
        symbols = {"files": [{"archive": name, "archive_sha256": self.digests[name]}
                             for name in self.names]}
        symbols.update(symbol_updates or {})
        diagnostics = {"schema_version": 1, "platform": "windows", "architecture": "x86_64",
                      "postgresql_version": "18.6", "pgvector_version": "0.8.7",
                      "archives": self.digests,
                      "system_failure": {"kind": "missing-bundled-runtime-dll", "failure_text": "failed as expected",
                                         "exit_code": -1073741515, "missing_library": "libxml2.dll", "ntstatus": "0xC0000135"},
                      "postgresql_failure": {"kind": "server-error", "failure_text": "division by zero",
                                             "exit_code": 3, "server_log": "ERROR: division by zero"}}
        diagnostics.update(diagnostic_updates or {})
        self.static.write_text(json.dumps(static))
        self.symbols.write_text(json.dumps(symbols))
        self.diagnostics.write_text(json.dumps(diagnostics))

    def emit(self):
        return emitter.emit(self.root, self.archives, self.output, "18.6", "a" * 40,
                            "10.0.20348.2402", "windows-2022-image", self.step_results,
                            self.static, self.symbols, self.diagnostics)

    def test_emits_two_records_bound_to_downloads_and_assembled_core(self):
        paths = self.emit()
        records = [json.loads(path.read_text()) for path in paths]
        self.assertEqual(len(records), 2)
        self.assertEqual([record["component"] for record in records], ["postgresql", "vector"])
        self.assertEqual(records[0]["scope"], "publication")
        self.assertEqual(records[0]["case_results"], {
            "archive-suite": "passed", "diagnostics": "passed", "symbols": "passed"})
        self.assertEqual(records[0]["sha256"], self.digests[self.names[0]])
        self.assertEqual(records[1]["sha256"], self.digests[self.names[1]])
        self.assertEqual(records[1]["assembled_core"], {
            "archive": self.names[0], "sha256": self.digests[self.names[0]], "version": "18.6"})
        self.assertEqual((records[0]["ci"]["source_revision"], records[0]["ci"]["build_run_id"],
                          records[0]["ci"]["build_run_attempt"]), ("b" * 40, "1234567", "2"))
        self.assertEqual((records[1]["ci"]["source_revision"], records[1]["ci"]["build_run_id"],
                          records[1]["ci"]["build_run_attempt"]), ("c" * 40, "7654321", "1"))
        for record in records:
            self.assertTrue(coverage.validate_verification_record(
                record, coverage.load_json(self.root / "support.json"), self.root))

    def test_aggregates_step_results_and_preserves_nonpassing_attempts(self):
        self.write_steps(**{"archive-suite": "failed", "symbols": "skipped"})
        paths = self.emit()
        for path in paths:
            record = json.loads(path.read_text())
            self.assertEqual(record["outcome"], "failed")
            self.assertEqual(record["case_results"]["symbols"], "skipped")

    def test_checks_sidecars_and_reports_against_exact_archive_bytes(self):
        sidecar = self.archives / f"{self.names[0]}.sha256"
        sidecar.write_text("0" * 64 + "  " + self.names[0] + "\n")
        with self.assertRaisesRegex(coverage.CoverageError, "sidecar"):
            self.emit()
        self.assertFalse(self.output.exists())

    def test_passed_records_require_all_three_reports(self):
        self.static.unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "PE static report is required"):
            self.emit()
        self.write_reports(static_updates={"outcome": "failed"})
        with self.assertRaisesRegex(coverage.CoverageError, "did not pass"):
            self.emit()
        self.write_reports(symbol_updates={"files": []})
        with self.assertRaisesRegex(coverage.CoverageError, "files must be nonempty"):
            self.emit()
        self.write_reports(diagnostic_updates={"archives": {}})
        with self.assertRaisesRegex(coverage.CoverageError, "diagnostic report archives"):
            self.emit()

    def test_rejects_incomplete_or_unknown_step_results(self):
        self.step_results.write_text(json.dumps({"diagnostics": "passed", "symbols": "passed"}))
        with self.assertRaisesRegex(coverage.CoverageError, "exactly every"):
            self.emit()
        self.write_steps(**{"symbols": "running"})
        with self.assertRaisesRegex(coverage.CoverageError, "passed, failed, or skipped"):
            self.emit()


if __name__ == "__main__":
    unittest.main()
