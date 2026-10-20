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
import import_windows_publication as importer


ROOT = Path(__file__).resolve().parents[1]


class WindowsPublicationImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        shutil.copytree(ROOT / "support", self.root / "support")
        shutil.copy(ROOT / "support.json", self.root / "support.json")
        shutil.copytree(ROOT / ".github", self.root / ".github")
        shutil.copytree(ROOT / "scripts", self.root / "scripts")
        shutil.copytree(ROOT / "tests", self.root / "tests")
        shutil.copytree(ROOT / "tools", self.root / "tools")
        self.build = Path(self.temp.name) / "windows-postgresql-18.6-pilot"
        self.verify = Path(self.temp.name) / "windows-postgresql-18.6-pilot-verification"
        (self.build / "debug-symbols").mkdir(parents=True)
        (self.verify / "verification-records" / "publication").mkdir(parents=True)
        self.run_id = "7654321"
        self.names = ["postgresql-18.6-windows-x86_64.tar.gz",
                      "pgvector-0.8.7-postgresql-18.6-windows-x86_64.tar.gz"]
        self.digests = {}
        archive_metadata = [
            ("postgresql/manifest.json", {"source_revision": "b" * 40, "build_id": "github-1234567-2"}),
            ("metadata.json", {"source_revision": "c" * 40, "build_id": "github-7654321-1"}),
        ]
        for name, (member_name, value) in zip(self.names, archive_metadata):
            buffer = io.BytesIO()
            payload = json.dumps(value).encode()
            with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
                member = tarfile.TarInfo(member_name)
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            data = buffer.getvalue()
            (self.build / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.digests[name] = digest
            (self.build / (name + ".sha256")).write_text(f"{digest}  {name}\n")
        (self.build / "debug-symbols" / "index.json").write_text(json.dumps({"files": [
            {"archive": name, "archive_sha256": self.digests[name]} for name in self.names]}))
        self._report("verification-records/static-analysis.json", {
            "outcome": "passed", "platform": "windows", "architecture": "x86_64",
            "inspected_files": ["bin/postgres.exe"],
            "archives": [{"basename": name, "sha256": self.digests[name]} for name in self.names]})
        self._report("verification-records/diagnostics.json", {
            "schema_version": 1, "platform": "windows", "architecture": "x86_64",
            "postgresql_version": "18.6", "pgvector_version": "0.8.7", "archives": self.digests,
            "system_failure": {"kind": "missing-bundled-runtime-dll", "exit_code": -1,
                               "missing_library": "libxml2.dll", "failure_text": "missing"},
            "postgresql_failure": {"kind": "server-error", "exit_code": 1,
                                   "failure_text": "server error", "server_log": "ERROR"}})
        self._report("verification-records/publication-attempt.json", {
            "run_id": self.run_id, "source_revision": "a" * 40,
            "steps": {"archive-suite": "success", "symbols": "success", "diagnostics": "success"}})
        outcomes = {"archive-suite": "passed", "symbols": "passed", "diagnostics": "passed"}
        self._report("verification-records/publication-steps.json", outcomes)
        env_keys = ("GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL")
        self.old_env = {key: os.environ.get(key) for key in env_keys}
        self.addCleanup(self._restore_env)
        os.environ.update({"GITHUB_RUN_ID": self.run_id, "GITHUB_REPOSITORY": "owner/repo",
                           "GITHUB_SERVER_URL": "https://github.com"})
        paths = emitter.emit(self.root, self.build,
            self.verify / "verification-records" / "publication", "18.6", "a" * 40,
            "10.0.20348.2402", "win22/20261012.333.1",
            self.verify / "verification-records" / "publication-steps.json",
            self.verify / "verification-records" / "static-analysis.json",
            self.build / "debug-symbols" / "index.json",
            self.verify / "verification-records" / "diagnostics.json")
        self.record_paths = paths

    def _restore_env(self):
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def tearDown(self):
        self.temp.cleanup()

    def _report(self, relative, value):
        path = self.verify / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def import_evidence(self):
        return importer.import_run(self.root, self.build, self.verify, self.run_id)

    def remove_archive_bound_outputs(self, result="failure", omit_steps=False):
        for name in self.names:
            (self.build / name).unlink()
            (self.build / (name + ".sha256")).unlink()
        (self.build / "debug-symbols" / "index.json").unlink()
        for path in self.record_paths:
            path.unlink()
        attempt_path = self.verify / "verification-records" / "publication-attempt.json"
        attempt = json.loads(attempt_path.read_text())
        attempt["steps"]["archive-suite"] = result
        attempt_path.write_text(json.dumps(attempt))
        steps_path = self.verify / "verification-records" / "publication-steps.json"
        if omit_steps:
            steps_path.unlink()
        else:
            outcomes = {case: "passed" if value == "success" else "failed" if value == "failure" else "skipped"
                        for case, value in attempt["steps"].items()}
            steps_path.write_text(json.dumps(outcomes))

    def test_imports_actual_nested_artifact_layout_and_retains_reports_attempt_and_records(self):
        retained = self.import_evidence()
        self.assertEqual(len(retained), 7)
        evidence = self.root / "support/evidence" / f"windows-publication-{self.run_id}"
        self.assertEqual(json.loads((evidence / "publication-attempt.json").read_text())["run_id"], self.run_id)
        self.assertTrue((evidence / "debug-symbols-index.json").is_file())
        self.assertEqual(len(list((self.root / "support/verification").glob(f"*-current-{self.run_id}.json"))), 2)

    def test_import_rejects_ci_provenance_that_does_not_match_reused_core_archive(self):
        core_path = next(path for path in self.record_paths if "postgresql-" in path.name)
        record = json.loads(core_path.read_text())
        record["ci"]["build_run_id"] = self.run_id
        record["ci"]["source_revision"] = "a" * 40
        record["ci"]["build_revision"] = "a" * 40
        core_path.write_text(json.dumps(record))
        with self.assertRaisesRegex(coverage.CoverageError, "CI provenance"):
            self.import_evidence()

    def test_rejects_changed_checksum_sidecar_without_retaining_partial_evidence(self):
        (self.build / (self.names[0] + ".sha256")).write_text("0" * 64 + "  " + self.names[0] + "\n")
        with self.assertRaisesRegex(coverage.CoverageError, "sidecar"):
            self.import_evidence()
        self.assertFalse((self.root / "support/evidence" / f"windows-publication-{self.run_id}").exists())

    def test_rejects_record_core_assembly_mismatch(self):
        vector_path = next(path for path in self.record_paths if "pgvector" in path.name)
        record = json.loads(vector_path.read_text())
        record["assembled_core"]["sha256"] = "0" * 64
        vector_path.write_text(json.dumps(record))
        with self.assertRaisesRegex(coverage.CoverageError, "core archive"):
            self.import_evidence()

    def test_refuses_to_overwrite_different_retained_attempt(self):
        target = self.root / "support/evidence" / f"windows-publication-{self.run_id}" / "publication-attempt.json"
        target.parent.mkdir(parents=True)
        target.write_text("different evidence")
        with self.assertRaisesRegex(coverage.CoverageError, "refusing to replace"):
            self.import_evidence()

    def test_retains_failed_raw_attempt_without_archives_or_publication_records(self):
        self.remove_archive_bound_outputs("failure")
        retained = self.import_evidence()
        self.assertEqual(len(retained), 2)
        evidence = self.root / "support/evidence" / f"windows-publication-{self.run_id}"
        attempt = json.loads((evidence / "publication-attempt.json").read_text())
        self.assertEqual(attempt["steps"]["archive-suite"], "failure")
        self.assertEqual(json.loads((evidence / "publication-steps.json").read_text())["archive-suite"], "failed")
        self.assertFalse(list((self.root / "support/verification").glob(f"*-current-{self.run_id}.json")))

    def test_retains_skipped_attempt_when_steps_file_is_absent(self):
        self.remove_archive_bound_outputs("skipped", omit_steps=True)
        retained = self.import_evidence()
        self.assertEqual(len(retained), 1)
        evidence = self.root / "support/evidence" / f"windows-publication-{self.run_id}"
        self.assertTrue((evidence / "publication-attempt.json").is_file())
        self.assertFalse((evidence / "publication-steps.json").exists())
        self.assertFalse(list((self.root / "support/verification").glob(f"*-current-{self.run_id}.json")))

    def test_rejects_invalid_unbound_attempt_identity_cases_and_passing_outcome(self):
        self.remove_archive_bound_outputs("failure")
        path = self.verify / "verification-records" / "publication-attempt.json"
        attempt = json.loads(path.read_text())
        attempt["run_id"] = "wrong"
        path.write_text(json.dumps(attempt))
        with self.assertRaisesRegex(coverage.CoverageError, "identity"):
            self.import_evidence()
        attempt["run_id"] = self.run_id
        attempt["steps"].pop("symbols")
        path.write_text(json.dumps(attempt))
        with self.assertRaisesRegex(coverage.CoverageError, "cases"):
            self.import_evidence()
        attempt["steps"] = {"archive-suite": "success", "symbols": "success", "diagnostics": "success"}
        path.write_text(json.dumps(attempt))
        with self.assertRaisesRegex(coverage.CoverageError, "passing attempt"):
            self.import_evidence()

    def test_rejects_oversized_raw_attempt(self):
        self.remove_archive_bound_outputs("failure")
        path = self.verify / "verification-records" / "publication-attempt.json"
        path.write_text(json.dumps({"padding": "x" * importer.MAX_EVIDENCE_BYTES}))
        with self.assertRaisesRegex(coverage.CoverageError, "exceeds"):
            self.import_evidence()


if __name__ == "__main__":
    unittest.main()
