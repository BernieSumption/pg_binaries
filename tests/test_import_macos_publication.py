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
import import_macos_publication as importer

REPO = Path(__file__).resolve().parents[1]


class MacOSPublicationImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "root"
        (self.root / "support").mkdir(parents=True)
        (self.root / "policies").mkdir()
        shutil.copy(REPO / "support.json", self.root / "support.json")
        shutil.copy(REPO / "support/postgresql-releases.json", self.root / "support/postgresql-releases.json")
        shutil.copy(REPO / "policies/extensions.md", self.root / "policies/extensions.md")
        shutil.copy(REPO / "support/verification-profiles.json", self.root / "support/verification-profiles.json")
        profiles = json.loads((self.root / "support/verification-profiles.json").read_text())["profiles"]
        for architecture in ("arm64", "x86_64"):
            for source in profiles[f"macos-publication-current-{architecture}"]["sources"]:
                source_path = REPO / source
                target_path = self.root / source
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source_path, target_path)
        self.archives = Path(self.temp.name) / "archives"
        self.archives.mkdir()
        self.verification = Path(self.temp.name) / "verification-records"
        (self.verification / "publication").mkdir(parents=True)
        self.pg, self.arch = "18.6", "arm64"
        platform = f"macos-{self.arch}"
        self.names = [f"postgresql-{self.pg}-{platform}.tar.gz",
                      f"pgvector-0.8.7-postgresql-{self.pg}-{platform}.tar.gz"]
        self.digests = {}
        for index, name in enumerate(self.names):
            archive = self.archives / name
            archive.write_bytes(f"downloaded archive {index}".encode())
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.digests[name] = digest
            Path(f"{archive}.sha256").write_text(f"{digest}  {name}\n")
        self.static = self.verification / "static-analysis.json"
        self.diagnostic = self.verification / "diagnostics.json"
        self.attempt = self.verification / "publication-attempt.json"
        self.attempt.write_text(json.dumps({"run_id": "1234", "source_revision": "a" * 40,
            "steps": {"archive-suite": "success", "symbols": "success", "diagnostics": "success"}}))
        self.write_reports()
        self.old_env = {key: os.environ.get(key) for key in ("GITHUB_RUN_ID", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL")}
        os.environ.update({"GITHUB_RUN_ID": "1234", "GITHUB_REPOSITORY": "owner/repo", "GITHUB_SERVER_URL": "https://github.com"})
        paths = emitter.emit(self.root, self.archives, self.verification / "publication", self.pg,
            "a" * 40, "15.7", self.arch, "macos-15/ImageVersion=2026.01",
            {"archive-suite": "success", "symbols": "success", "diagnostics": "success"},
            self.static, self.diagnostic)
        self.records = paths
        self.addCleanup(self.restore_env)

    def restore_env(self):
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def tearDown(self):
        self.temp.cleanup()

    def write_reports(self):
        archive_list = [{"basename": name, "sha256": self.digests[name]} for name in self.names]
        self.static.write_text(json.dumps({"passed": True, "architecture": self.arch,
            "inspected_files": [{"file": "bin/postgres"}], "archives": archive_list}))
        self.diagnostic.write_text(json.dumps({"platform": "macos", "architecture": self.arch,
            "postgresql_version": self.pg, "pgvector_version": "0.8.7",
            "system_failure": {"exit_code": 1, "loader_output": "missing library"},
            "postgresql_failure": {"exit_code": 3, "server_log": "server error"},
            "archives": self.digests}))

    def test_imports_actual_workflow_artifact_layout_and_retains_records_reports_and_attempt(self):
        retained = importer.import_run(self.root, self.archives, self.verification, "1234", self.arch, self.pg)
        self.assertEqual(len(retained), 5)
        self.assertTrue((self.root / "support/evidence/macos-publication-1234/arm64/publication-attempt.json").is_file())
        records = [json.loads((self.root / "support/verification" / Path(path).name).read_text())
                   for path in retained if path.startswith("support/verification/")]
        self.assertEqual({record["component"] for record in records}, {"postgresql", "vector"})
        vector = next(record for record in records if record["component"] == "vector")
        self.assertEqual(vector["assembled_core"]["sha256"], self.digests[self.names[0]])

    def test_rejects_changed_sidecar_and_wrong_attempt_run(self):
        sidecar = self.archives / f"{self.names[0]}.sha256"
        original = sidecar.read_text()
        sidecar.write_text("0" * 64 + "  " + self.names[0] + "\n")
        with self.assertRaisesRegex(coverage.CoverageError, "checksum sidecar"):
            importer.import_run(self.root, self.archives, self.verification, "1234", self.arch, self.pg)
        sidecar.write_text(original)
        attempt = json.loads(self.attempt.read_text())
        attempt["run_id"] = "9999"
        self.attempt.write_text(json.dumps(attempt))
        with self.assertRaisesRegex(coverage.CoverageError, "attempt identity"):
            importer.import_run(self.root, self.archives, self.verification, "1234", self.arch, self.pg)

    def test_refuses_to_overwrite_different_retained_evidence(self):
        destination = self.root / "support/evidence/macos-publication-1234/arm64/publication-attempt.json"
        destination.parent.mkdir(parents=True)
        destination.write_text("different")
        with self.assertRaisesRegex(coverage.CoverageError, "refusing to replace"):
            importer.import_run(self.root, self.archives, self.verification, "1234", self.arch, self.pg)

    def test_retains_failed_and_skipped_attempts_without_archives_or_records(self):
        for run_id, outcome in (("2345", "failure"), ("3456", "skipped")):
            attempt = {"run_id": run_id, "source_revision": "b" * 40,
                       "steps": {"archive-suite": "success", "symbols": outcome,
                                 "diagnostics": "skipped" if outcome == "skipped" else "success"}}
            self.attempt.write_text(json.dumps(attempt))
            for record in self.records:
                if record.exists():
                    record.unlink()
            for archive in self.archives.iterdir():
                archive.unlink()
            retained = importer.import_run(self.root, self.archives, self.verification, run_id, self.arch, self.pg)
            self.assertEqual(len(retained), 1)
            copied = self.root / retained[0]
            self.assertEqual(json.loads(copied.read_text()), attempt)
            self.assertFalse((self.root / "support/verification").exists())

    def test_failed_attempt_still_checks_size_and_never_overwrites(self):
        attempt = {"run_id": "4567", "source_revision": "c" * 40,
                   "steps": {"archive-suite": "failure", "symbols": "skipped", "diagnostics": "skipped"}}
        self.attempt.write_text(json.dumps(attempt))
        for record in self.records:
            record.unlink()
        for archive in self.archives.iterdir():
            archive.unlink()
        destination = self.root / "support/evidence/macos-publication-4567/arm64/publication-attempt.json"
        destination.parent.mkdir(parents=True)
        destination.write_text("existing")
        with self.assertRaisesRegex(coverage.CoverageError, "refusing to replace"):
            importer.import_run(self.root, self.archives, self.verification, "4567", self.arch, self.pg)
        destination.unlink()
        self.attempt.write_text(" " * (importer.MAX_EVIDENCE_BYTES + 1))
        with self.assertRaisesRegex(coverage.CoverageError, "at most"):
            importer.import_run(self.root, self.archives, self.verification, "4567", self.arch, self.pg)


if __name__ == "__main__":
    unittest.main()
