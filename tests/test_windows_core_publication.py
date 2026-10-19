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
import emit_windows_core_publication as emitter
import import_windows_core_publication as importer


ROOT = Path(__file__).resolve().parents[1]


class WindowsCorePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        for name in ("support", ".github", "scripts", "tests", "tools"):
            shutil.copytree(ROOT / name, self.root / name)
        shutil.copy(ROOT / "support.json", self.root / "support.json")
        registry_path = self.root / "support/verification-profiles.json"
        registry = json.loads(registry_path.read_text())
        profile_id = "postgresql-publication-windows-x86_64-18.6"
        target_profile = dict(registry["profiles"]["windows-publication-current-x86_64"])
        target_profile["sources"] = sorted(set(target_profile["sources"] + [
            "tests/test_windows_core_publication.py", "tools/emit_windows_core_publication.py",
            "tools/import_windows_core_publication.py"]))
        registry["profiles"][profile_id] = target_profile
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        self.build = Path(self.temp.name) / "build"
        (self.build / "debug-symbols").mkdir(parents=True)
        self.verify = Path(self.temp.name) / "verification"
        self.verify.mkdir()
        self.pg = "18.6"
        self.run_id = "7654321"
        self.revision = "a" * 40
        self.archive_name = f"postgresql-{self.pg}-windows-x86_64.tar.gz"
        self.archive = self.build / self.archive_name
        self.archive.write_bytes(b"core archive bytes")
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        (self.build / (self.archive_name + ".sha256")).write_text(
            f"{self.digest}  {self.archive_name}\n", encoding="utf-8")
        self.pdb = self.build / "debug-symbols/pdbs/postgres.pdb"
        self.pdb.parent.mkdir(parents=True, exist_ok=True)
        self.pdb.write_bytes(b"PDB fixture")
        self.pdb_digest = hashlib.sha256(self.pdb.read_bytes()).hexdigest()
        self._write(self.build / "debug-symbols/index.json", {"schema_version": 1, "files": [{
            "archive": self.archive_name, "archive_sha256": self.digest,
            "module_path": "postgresql/bin/postgres.exe", "module_sha256": "b" * 64,
            "rsds_guid": "c" * 32, "rsds_age": 1, "pdb_path": "pdbs/postgres.pdb",
            "pdb_sha256": self.pdb_digest,
        }]})
        self.static = self.verify / "static-analysis.json"
        self.diagnostics = self.verify / "diagnostics.json"
        self._write(self.static, {"outcome": "passed", "platform": "windows", "architecture": "x86_64",
                                  "inspected_files": ["bin/postgres.exe"], "archives": [
                                      {"basename": self.archive_name, "sha256": self.digest}]})
        self._write(self.diagnostics, self.diagnostic_report())
        self.steps = self.verify / "step-results.json"
        self._write(self.steps, {"archive-suite": "passed", "symbols": "passed", "diagnostics": "passed"})
        self.old_env = {key: os.environ.get(key) for key in (
            "GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL")}
        os.environ.update({"GITHUB_RUN_ID": self.run_id, "GITHUB_REPOSITORY": "owner/repo",
                           "GITHUB_SERVER_URL": "https://github.com"})
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def diagnostic_report(self):
        return {"schema_version": 1, "platform": "windows", "architecture": "x86_64",
                "postgresql_version": self.pg, "archives": {self.archive_name: self.digest},
                "system_failure": {"kind": "missing-bundled-runtime-dll", "exit_code": -1,
                                   "missing_library": "libxml2.dll", "failure_text": "missing"},
                "postgresql_failure": {"kind": "server-error", "exit_code": 1,
                                       "failure_text": "server error", "server_log": "ERROR"}}

    def emit(self):
        return emitter.emit(self.root, self.build, self.verify / "publication", self.pg,
                            self.revision, "10.0.20348.2402", "win22/20261012.333.1",
                            self.steps, self.static, self.build / "debug-symbols/index.json",
                            self.diagnostics)

    def test_emits_and_imports_one_core_record_with_target_profile(self):
        emitted = self.emit()
        self.assertEqual(len(emitted), 1)
        record = json.loads(emitted[0].read_text())
        self.assertEqual(record["component"], "postgresql")
        self.assertEqual(record["profile_id"], "postgresql-publication-windows-x86_64-18.6")
        self.assertNotIn("project", record)
        self.assertNotIn("assembled_core", record)
        self.assertEqual(json.loads((self.verify / "publication/publication-attempt.json").read_text())["steps"], {
            "archive-suite": "success", "symbols": "success", "diagnostics": "success"})
        retained = importer.import_run(self.root, self.build, self.verify, self.run_id, self.pg)
        self.assertEqual(len(retained), 6)
        self.assertEqual(len(list((self.root / "support/verification").glob(
            f"postgresql-{self.pg}-windows-x86_64-current-{self.run_id}.json"))), 1)
        evidence = self.root / "support/evidence/windows-publication-7654321/postgresql-18.6"
        self.assertTrue((evidence / "debug-symbols-index.json").is_file())

    def test_rejects_bad_archive_sidecar(self):
        (self.build / (self.archive_name + ".sha256")).write_text("0" * 64 + "  " + self.archive_name + "\n")
        with self.assertRaisesRegex(coverage.CoverageError, "sidecar"):
            self.emit()

    def test_rejects_pdb_index_bound_to_another_archive(self):
        self._write(self.build / "debug-symbols/index.json", {"files": [{
            "archive": self.archive_name, "archive_sha256": "0" * 64}]})
        with self.assertRaisesRegex(coverage.CoverageError, "PDB index"):
            self.emit()

    def test_core_diagnostic_report_rejects_pgvector_identity(self):
        report = self.diagnostic_report()
        report["pgvector_version"] = "0.8.7"
        self._write(self.diagnostics, report)
        with self.assertRaisesRegex(coverage.CoverageError, "core diagnostic"):
            self.emit()

    def test_rejects_diagnostic_bound_to_another_core_archive(self):
        report = self.diagnostic_report()
        report["archives"][self.archive_name] = "0" * 64
        self._write(self.diagnostics, report)
        with self.assertRaisesRegex(coverage.CoverageError, "diagnostic report archive"):
            self.emit()

    def test_failed_or_skipped_raw_attempt_can_be_retained_without_archive(self):
        self.archive.unlink()
        Path(str(self.archive) + ".sha256").unlink()
        self._write(self.steps, {"archive-suite": "failed", "symbols": "skipped", "diagnostics": "skipped"})
        output = self.verify / "raw-only"
        self.assertEqual(emitter.emit(self.root, self.build, output, self.pg, self.revision,
                         "10.0.20348.2402", "win22/20261012.333.1", self.steps), [])
        self.assertEqual(importer.import_run(self.root, self.build, output, self.run_id, self.pg), [
            "support/evidence/windows-publication-7654321/postgresql-18.6/publication-attempt.json",
            "support/evidence/windows-publication-7654321/postgresql-18.6/publication-steps.json"])
        raw = json.loads((self.root / "support/evidence/windows-publication-7654321/postgresql-18.6/publication-attempt.json").read_text())
        self.assertEqual(raw["steps"]["archive-suite"], "failure")

    def test_import_rejects_conflicting_retained_bytes(self):
        self.emit()
        target = self.root / "support/evidence/windows-publication-7654321/postgresql-18.6/publication-steps.json"
        target.parent.mkdir(parents=True)
        target.write_text("different")
        with self.assertRaisesRegex(coverage.CoverageError, "refusing to replace"):
            importer.import_run(self.root, self.build, self.verify, self.run_id, self.pg)

    def test_import_rejects_record_bound_to_another_archive(self):
        record_path = self.emit()[0]
        record = json.loads(record_path.read_text())
        record["sha256"] = "0" * 64
        self._write(record_path, record)
        with self.assertRaisesRegex(coverage.CoverageError, "archive digest"):
            importer.import_run(self.root, self.build, self.verify, self.run_id, self.pg)

    def test_import_requires_reports_for_a_passed_record(self):
        self.emit()
        self.static.unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "requires PE report"):
            importer.import_run(self.root, self.build, self.verify, self.run_id, self.pg)

    def test_requires_registered_target_profile(self):
        registry_path = self.root / "support/verification-profiles.json"
        registry = json.loads(registry_path.read_text())
        registry["profiles"].pop("postgresql-publication-windows-x86_64-18.6")
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        with self.assertRaisesRegex(coverage.CoverageError, "registered target profile"):
            self.emit()


if __name__ == "__main__":
    unittest.main()
