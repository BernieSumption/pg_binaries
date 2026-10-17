import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import coverage
import create_extension_publication_receipt as receipt_creator
import emit_extension_publication_records as emitter
import import_linux_pgaudit_publication as importer


class LinuxPgauditPublicationImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "root"
        (self.root / "support").mkdir(parents=True)
        for source in ("support.json", "support/verification-profiles.json",
                       "support/postgresql-releases.json"):
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / source, destination)
        registry_path = self.root / "support/verification-profiles.json"
        registry = json.loads(registry_path.read_text())
        for architecture in ("x86_64", "arm64"):
            registry["profiles"][f"pgaudit-publication-current-{architecture}"] = {
                "scope": "publication", "case_ids": ["pgaudit-archive-suite"],
                "platforms": [f"linux-{architecture}"], "sources": ["support.json"],
            }
        registry_path.write_text(json.dumps(registry))

        self.run_id = "7654321"
        self.architecture = "x86_64"
        self.platform = "linux-x86_64"
        self._configure_target("18.6")

    def _configure_target(self, postgresql_version):
        self.postgresql_version = postgresql_version
        major = int(postgresql_version.split(".", 1)[0])
        self.pgaudit_version = {15: "1.7.1", 16: "16.1", 17: "17.1", 18: "18.0"}[major]
        shutil.rmtree(self.base / "core-artifact", ignore_errors=True)
        shutil.rmtree(self.base / "pgaudit-artifact", ignore_errors=True)
        shutil.rmtree(self.root / "support/evidence", ignore_errors=True)
        shutil.rmtree(self.root / "support/verification", ignore_errors=True)
        self.core_artifact = self.base / "core-artifact"
        self.pgaudit_artifact = self.base / "pgaudit-artifact"
        self.core_dir = self.core_artifact / "pilot"
        self.core_dir.mkdir(parents=True)
        self.pgaudit_artifact.mkdir()
        self._make_archives()
        self.publication = self.pgaudit_artifact / "pgaudit-publication"
        self.records_dir = self.publication / "records"
        self.records_dir.mkdir(parents=True)
        self._make_publication()

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    @classmethod
    def _archive(cls, path, metadata=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(path, "w:gz") as archive:
            if metadata is not None:
                from io import BytesIO
                data = json.dumps(metadata).encode()
                member = tarfile.TarInfo("metadata.json")
                member.size = len(data)
                archive.addfile(member, BytesIO(data))
        path.with_name(path.name + ".sha256").write_text(
            f"{cls._sha(path)}  {path.name}\n", encoding="utf-8")

    def _make_archives(self):
        self.core_name = f"postgresql-{self.postgresql_version}-{self.platform}.tar.gz"
        self.pgaudit_name = f"pgaudit-{self.pgaudit_version}-postgresql-{self.postgresql_version}-{self.platform}.tar.gz"
        self._archive(self.core_dir / self.core_name)
        self._archive(self.pgaudit_artifact / self.pgaudit_name, {
            "project": "pgaudit", "version": self.pgaudit_version,
            "postgresql_version": self.postgresql_version,
            "platform": "linux", "architecture": self.architecture,
            "sql_names": ["pgaudit"], "requires": [],
            "source": dict(zip(("url", "sha256"),
                                importer.PGAUDIT_SOURCE_IDENTITIES[self.pgaudit_version])),
        })
        report = self.pgaudit_artifact / "static-analysis/pgaudit.json"
        report.parent.mkdir()
        report.write_text(json.dumps({
            "outcome": "passed", "architecture": self.architecture,
            "files": [{"path": "pgaudit/lib/pgaudit.so", "architecture": self.architecture,
                       "interpreter": "none", "runtime_search_paths": []}],
            "archives": [
                {"basename": self.core_name, "sha256": self._sha(self.core_dir / self.core_name)},
                {"basename": self.pgaudit_name, "sha256": self._sha(self.pgaudit_artifact / self.pgaudit_name)},
            ],
        }))

    def _make_publication(self, result="success"):
        profile_id = f"pgaudit-publication-current-{self.architecture}"
        image = "sha256:" + "b" * 64
        step_outcomes = {
            "success": {"core_build": "success", "pgaudit_build": "success", "pgaudit_verify": "success"},
            "failed": {"core_build": "success", "pgaudit_build": "success", "pgaudit_verify": "failure"},
            "skipped": {"core_build": "success", "pgaudit_build": "skipped", "pgaudit_verify": "skipped"},
        }[result]
        suite = {"success": "success", "failed": "failure", "skipped": "skipped"}[result]
        attempt_path = self.publication / "attempt.json"
        attempt_path.write_text(json.dumps({
            "schema_version": 1, "run_id": self.run_id, "source_revision": "a" * 40,
            "postgresql_version": self.postgresql_version, "pgaudit_version": self.pgaudit_version,
            "architecture": self.architecture, "verifier_image_id": image,
            "steps": step_outcomes,
        }))
        steps_path = self.publication / "current-steps.json"
        steps_path.write_text(json.dumps({"pgaudit-archive-suite": suite}))
        receipt_path = self.publication / "current-receipt.json"
        receipt_creator.create(
            self.root, self.pgaudit_artifact, self.core_dir, receipt_path, profile_id,
            "pgaudit", self.pgaudit_version, self.postgresql_version, self.postgresql_version,
            self.architecture, "current", "6.8.0-test-kernel", "Alpine Linux", "3.22.6",
            image, "success" if result == "success" else "failure", result == "success",
            steps_path, environ={"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": self.run_id,
                                 "GITHUB_REPOSITORY": "example/repo",
                                 "GITHUB_SERVER_URL": "https://github.com"})
        emitter.emit(self.root, self.pgaudit_artifact, self.core_dir, receipt_path, self.records_dir)

    def _import(self):
        return importer.import_run(self.root, self.core_artifact, self.pgaudit_artifact,
                                   self.run_id, self.architecture, self.postgresql_version)

    def test_retains_archive_bound_evidence_idempotently(self):
        retained = self._import()
        record_path = self.root / "support/verification" / (
            f"pgaudit-{self.pgaudit_version}-postgresql-{self.postgresql_version}-{self.platform}-current-{self.run_id}.json")
        record = json.loads(record_path.read_text())
        self.assertEqual(record["assembled_core"]["sha256"], self._sha(self.core_dir / self.core_name))
        self.assertEqual(record["sha256"], self._sha(self.pgaudit_artifact / self.pgaudit_name))
        self.assertEqual(len(retained), 5)
        self.assertEqual(self._import(), retained)

    def test_retains_failed_and_skipped_records_as_nonpassing(self):
        for result in ("failed", "skipped"):
            with self.subTest(result=result):
                shutil.rmtree(self.root / "support/evidence", ignore_errors=True)
                shutil.rmtree(self.root / "support/verification", ignore_errors=True)
                shutil.rmtree(self.records_dir)
                self._make_publication(result)
                self._import()
                record = json.loads(next((self.root / "support/verification").glob("*.json")).read_text())
                self.assertEqual(record["outcome"], result)

    def test_imports_each_selected_postgresql_major_and_pgaudit_release(self):
        for pg_version, pgaudit_version in (("15.19", "1.7.1"), ("16.15", "16.1"),
                                            ("17.11", "17.1"), ("18.6", "18.0")):
            with self.subTest(postgresql_version=pg_version):
                self._configure_target(pg_version)
                self.assertEqual(self.pgaudit_version, pgaudit_version)
                self._import()
                record = json.loads(next((self.root / "support/verification").glob("*.json")).read_text())
                self.assertEqual(record["postgresql_version"], pg_version)
                self.assertEqual(record["version"], pgaudit_version)

    def test_rejects_attempt_from_another_pgaudit_major(self):
        attempt_path = self.publication / "attempt.json"
        attempt = json.loads(attempt_path.read_text())
        attempt["pgaudit_version"] = "17.1"
        attempt_path.write_text(json.dumps(attempt))
        with self.assertRaises(coverage.CoverageError):
            self._import()

    def test_rejects_extension_with_wrong_upstream_source_digest(self):
        self._archive(self.pgaudit_artifact / self.pgaudit_name, {
            "project": "pgaudit", "version": self.pgaudit_version,
            "postgresql_version": self.postgresql_version,
            "platform": "linux", "architecture": self.architecture,
            "sql_names": ["pgaudit"], "requires": [],
            "source": {"url": "https://example.invalid/archive.tar.gz", "sha256": "0" * 64},
        })
        report = self.pgaudit_artifact / "static-analysis/pgaudit.json"
        data = json.loads(report.read_text())
        data["archives"][1]["sha256"] = self._sha(self.pgaudit_artifact / self.pgaudit_name)
        report.write_text(json.dumps(data))
        self._make_publication()
        with self.assertRaises(coverage.CoverageError):
            self._import()

    def test_retains_only_attempt_when_archives_are_missing(self):
        for path in (self.core_dir / self.core_name,
                     self.pgaudit_artifact / self.pgaudit_name):
            path.unlink()
            path.with_name(path.name + ".sha256").unlink()
        (self.pgaudit_artifact / "static-analysis/pgaudit.json").unlink()
        shutil.rmtree(self.records_dir)
        (self.publication / "current-receipt.json").unlink()
        (self.publication / "current-steps.json").write_text('{"pgaudit-archive-suite":"skipped"}')
        attempt = json.loads((self.publication / "attempt.json").read_text())
        attempt["steps"] = {"core_build": "failure", "pgaudit_build": "skipped", "pgaudit_verify": "skipped"}
        (self.publication / "attempt.json").write_text(json.dumps(attempt))
        self.assertEqual(len(self._import()), 2)


if __name__ == "__main__":
    unittest.main()
