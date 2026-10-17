import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
import emit_macos_publication_records as emitter

REPO = Path(__file__).resolve().parents[1]


class MacOSPublicationRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "root"
        (self.root / "support").mkdir(parents=True)
        (self.root / "policies").mkdir()
        shutil.copy(REPO / "support.json", self.root / "support.json")
        shutil.copy(REPO / "support/postgresql-releases.json", self.root / "support/postgresql-releases.json")
        shutil.copy(REPO / "policies/extensions.md", self.root / "policies/extensions.md")
        self.archives = Path(self.temp.name) / "archives"
        self.archives.mkdir()
        self.output = Path(self.temp.name) / "records"
        self.source = self.root / "workflow.yml"
        self.source.write_text("publication verifier\n")
        profiles = {}
        for arch in ("x86_64", "arm64"):
            profiles[f"macos-publication-current-{arch}"] = {
                "scope": "publication", "platforms": [f"macos-{arch}"],
                "case_ids": ["archive-suite", "diagnostics", "symbols"],
                "sources": ["workflow.yml"],
            }
        (self.root / "support/verification-profiles.json").write_text(json.dumps({"schema_version": 1, "profiles": profiles}))
        self.arch = "x86_64"
        self.pg = "18.6"
        self.names = [f"postgresql-{self.pg}-macos-{self.arch}.tar.gz",
                      f"pgvector-0.8.7-postgresql-{self.pg}-macos-{self.arch}.tar.gz"]
        self.digests = {}
        for idx, name in enumerate(self.names):
            data = f"archive bytes {idx}".encode()
            (self.archives / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.digests[name] = digest
            (self.archives / f"{name}.sha256").write_text(f"{digest}  {name}\n")
        self.static = Path(self.temp.name) / "static.json"
        self.diagnostic = Path(self.temp.name) / "diagnostics.json"
        self.write_reports()
        self.old_env = {key: os.environ.get(key) for key in ("GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL")}
        os.environ.update({"GITHUB_RUN_ID": "1234", "GITHUB_REPOSITORY": "owner/repo", "GITHUB_SERVER_URL": "https://github.com"})
        self.addCleanup(self.restore_env)

    def restore_env(self):
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def tearDown(self):
        self.temp.cleanup()

    def write_reports(self, **updates):
        archives = [{"basename": name, "sha256": self.digests[name]} for name in self.names]
        static = {"passed": True, "architecture": self.arch, "inspected_files": [{"file": "bin/postgres"}], "archives": archives}
        diagnostic = {"platform": "macos", "architecture": self.arch, "postgresql_version": self.pg,
                      "pgvector_version": "0.8.7", "system_failure": {"kind": "loader", "exit_code": 1,
                      "loader_output": "Library not loaded"},
                      "postgresql_failure": {"kind": "server-error", "exit_code": 3,
                      "server_log": "ERROR: division by zero"},
                      "archives": {name: self.digests[name] for name in self.names}}
        static.update(updates)
        self.static.write_text(json.dumps(static))
        self.diagnostic.write_text(json.dumps(diagnostic))

    def emit(self, **kw):
        return emitter.emit(self.root, self.archives, self.output, self.pg, "a" * 40,
                            "15.7", self.arch, "macos-15/ImageVersion=2026.01",
                            {"archive-suite": "success", "symbols": "success", "diagnostics": "success"},
                            self.static, self.diagnostic, **kw)

    def test_emits_records_bound_to_archives_project_and_assembled_core(self):
        paths = self.emit()
        self.assertEqual(len(paths), 2)
        records = [json.loads(path.read_text()) for path in paths]
        self.assertEqual([r["component"] for r in records], ["postgresql", "vector"])
        self.assertEqual(records[1]["project"], "pgvector")
        self.assertEqual(records[1]["assembled_core"]["sha256"], self.digests[self.names[0]])
        self.assertEqual(records[1]["case_results"], {"archive-suite": "passed", "symbols": "passed", "diagnostics": "passed"})
        for record in records:
            self.assertTrue(coverage.validate_verification_record(record, coverage.load_json(self.root / "support.json"), self.root))

    def test_aggregates_failure_and_skip_from_supplied_steps(self):
        for status, outcome in (("failure", "failed"), ("skipped", "skipped")):
            results = {"archive-suite": "success", "symbols": status, "diagnostics": "success"}
            paths = emitter.emit(self.root, self.archives, self.output, self.pg, "a" * 40, "15.7", self.arch,
                                 "macos-15/ImageVersion=2026.01", results, None, None)
            self.assertEqual(json.loads(paths[0].read_text())["outcome"], outcome)
            for path in paths:
                path.unlink()

    def test_passed_records_require_static_and_diagnostic_reports_bound_to_exact_bytes(self):
        self.static.unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "static analysis report is required"):
            self.emit()
        self.write_reports(architecture="arm64")
        with self.assertRaisesRegex(coverage.CoverageError, "static analysis report architecture"):
            self.emit()
        self.write_reports()
        report = json.loads(self.diagnostic.read_text())
        report["archives"][self.names[0]] = "0" * 64
        self.diagnostic.write_text(json.dumps(report))
        with self.assertRaisesRegex(coverage.CoverageError, "diagnostic report archives"):
            self.emit()

    def test_rejects_sidecar_and_case_set_mismatches(self):
        (self.archives / f"{self.names[0]}.sha256").write_text("0" * 64 + "  " + self.names[0] + "\n")
        with self.assertRaisesRegex(coverage.CoverageError, "checksum sidecar"):
            self.emit()
        (self.archives / f"{self.names[0]}.sha256").write_text(self.digests[self.names[0]] + "  " + self.names[0] + "\n")
        with self.assertRaisesRegex(coverage.CoverageError, "exactly the archive-suite"):
            (self.root / "support/verification-profiles.json").write_text(json.dumps({"schema_version": 1, "profiles": {
                "macos-publication-current-x86_64": {"scope": "publication", "platforms": ["macos-x86_64"],
                    "case_ids": ["archive-suite", "diagnostics"], "sources": ["workflow.yml"]}}}))
            self.emit()


if __name__ == "__main__":
    unittest.main()
