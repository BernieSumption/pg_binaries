import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
import create_extension_publication_receipt as receipt_creator
import emit_extension_publication_records as emitter
import import_linux_collection_publication as importer
import linux_core_resolution


REPO = Path(__file__).resolve().parents[1]
VERSIONS = ("1.1.1", "2.1.3")
SOURCE_SHA256 = {
    "1.1.1": "ab99a969334442e4a3c77405bc9ffed0083595d18f3898d64a731353a32bec5e",
    "2.1.3": "a6b07864e5893d3b682bb3223fd6d33015709765c9d40d415c85112358f0e3e4",
}


class CollectionPublicationImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "root"
        (self.root / "support").mkdir(parents=True)
        shutil.copy(REPO / "support.json", self.root / "support.json")
        shutil.copy(REPO / "support/postgresql-releases.json",
                    self.root / "support/postgresql-releases.json")
        (self.root / "profile-source.txt").write_text("profile source\n")
        self.architecture = "x86_64"
        self.platform = f"linux-{self.architecture}"
        profile_id = f"collection-publication-current-{self.architecture}"
        (self.root / "support/verification-profiles.json").write_text(json.dumps({
            "schema_version": 1, "profiles": {profile_id: {
                "scope": "publication", "platforms": [self.platform],
                "case_ids": ["collection-archive-suite"], "sources": ["profile-source.txt"],
            }},
        }))
        self.core_artifact = self.base / "core"
        self.core_dir = self.core_artifact / "pilot"
        self.collection_artifact = self.base / "collection"
        self.publication = self.collection_artifact / "collection-publication"
        self.records = self.publication / "records"
        self.core_dir.mkdir(parents=True)
        self.records.mkdir(parents=True)
        self.core_name = f"postgresql-18.6-{self.platform}.tar.gz"
        (self.core_dir / self.core_name).write_bytes(b"core fixture")
        self.extension_names = {}
        self.extension_hashes = {}
        for version in VERSIONS:
            name = f"collection-{version}-postgresql-18.6-{self.platform}.tar.gz"
            self.extension_names[version] = name
            metadata = {
                "project": "collection", "version": version, "sql_names": ["collection"],
                "requires": [], "postgresql_version": "18.6", "platform": "linux",
                "architecture": self.architecture,
                "source": {"url": f"https://github.com/aws/pgcollection/archive/refs/tags/v{version}.tar.gz",
                           "sha256": SOURCE_SHA256[version]},
            }
            with tarfile.open(self.collection_artifact / name, "w:gz") as archive:
                data = json.dumps(metadata).encode()
                member = tarfile.TarInfo("metadata.json")
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            self.extension_hashes[version] = self._sidecar(self.collection_artifact / name)
        self.core_hash = self._sidecar(self.core_dir / self.core_name)
        self.profile_id = f"collection-publication-current-{self.architecture}"
        self.run_id = "456"
        self.revision = "a" * 40
        self.image_id = "sha256:" + "b" * 64
        self._make_attempt()
        self._make_receipts_and_records()
        for version in VERSIONS:
            report = self.collection_artifact / "static-analysis" / f"collection-{version}.json"
            report.parent.mkdir(exist_ok=True)
            report.write_text(json.dumps({
                "outcome": "passed", "architecture": self.architecture,
                "files": [{"path": "collection/lib/collection.so"}],
                "archives": [
                    {"basename": self.core_name, "sha256": self.core_hash},
                    {"basename": self.extension_names[version], "sha256": self.extension_hashes[version]},
                ],
            }))

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _sidecar(path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n")
        return digest

    def _make_attempt(self):
        (self.publication / "attempt.json").write_text(json.dumps({
            "schema_version": 1, "run_id": self.run_id, "source_revision": self.revision,
            "postgresql_version": "18.6", "collection_versions": list(VERSIONS),
            "source_sha256": SOURCE_SHA256, "architecture": self.architecture,
            "verifier_image_id": self.image_id,
            "steps": {"core_build": "success", "collection_build": "success",
                      "collection_verify": "success"},
        }))
        (self.publication / "current-steps.json").write_text(
            json.dumps({"collection-archive-suite": "success"}))

    def _make_receipts_and_records(self):
        for version in VERSIONS:
            receipt_path = self.publication / f"current-receipt-{version}.json"
            profile = coverage.verification_profile(self.root, self.profile_id)
            receipt_creator.create(
                self.root, self.collection_artifact, self.core_dir, receipt_path, self.profile_id,
                "collection", version, "18.6", "18.6", self.architecture, "current",
                "6.8.0-test-kernel", "Alpine Linux", "3.22.6", self.image_id,
                "success", True, self.publication / "current-steps.json",
                environ={"GITHUB_SHA": self.revision, "GITHUB_RUN_ID": self.run_id,
                         "GITHUB_REPOSITORY": "example/repo", "GITHUB_SERVER_URL": "https://github.com"})
            emitter.emit(self.root, self.collection_artifact, self.core_dir, receipt_path,
                         self.records)

    def _import(self):
        return importer.import_run(self.root, self.core_artifact, self.collection_artifact,
                                   self.run_id, self.architecture)

    def test_retains_both_archive_bound_records_and_static_reports(self):
        retained = self._import()
        self.assertEqual(len(retained), 8)
        paths = sorted((self.root / "support/verification").glob("*.json"))
        self.assertEqual({json.loads(path.read_text())["version"] for path in paths}, set(VERSIONS))
        for path in paths:
            record = json.loads(path.read_text())
            self.assertEqual(record["assembled_core"]["sha256"], self.core_hash)
            coverage.validate_verification_record(record, coverage.load_json(self.root / "support.json"), self.root)
        self.assertEqual(self._import(), retained)

    def test_rejects_wrong_pinned_source_and_archive_checksum(self):
        attempt = json.loads((self.publication / "attempt.json").read_text())
        attempt["source_sha256"]["1.1.1"] = "0" * 64
        (self.publication / "attempt.json").write_text(json.dumps(attempt))
        with self.assertRaisesRegex(coverage.CoverageError, "source pins"):
            self._import()
        self._make_attempt()
        receipt_path = self.publication / "current-receipt-1.1.1.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["archives"][self.extension_names["1.1.1"]] = "0" * 64
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(coverage.CoverageError, "receipt identity or archive hashes"):
            self._import()

    def test_rejects_a_postgresql_version_outside_the_selected_release_set(self):
        with self.assertRaisesRegex(coverage.CoverageError, "PostgreSQL 18.7 is not selected"):
            importer.import_run(self.root, self.core_artifact, self.collection_artifact,
                                self.run_id, self.architecture, "18.7")

    def test_rejects_record_with_a_different_archive_checksum(self):
        path = next(self.records.glob("collection-1.1.1-*.json"))
        record = json.loads(path.read_text())
        record["sha256"] = "0" * 64
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(coverage.CoverageError, "record identity or archive checksum"):
            self._import()

    def test_retains_raw_failure_without_a_receipt(self):
        shutil.rmtree(self.records)
        self.records.mkdir()
        for path in self.publication.glob("current-receipt-*.json"):
            path.unlink()
        (self.publication / "current-steps.json").write_text(
            json.dumps({"collection-archive-suite": "failure"}))
        attempt = json.loads((self.publication / "attempt.json").read_text())
        attempt["steps"]["collection_verify"] = "failure"
        (self.publication / "attempt.json").write_text(json.dumps(attempt))
        retained = self._import()
        self.assertEqual(len(retained), 4)
        self.assertTrue((self.root / "support/evidence" / f"collection-publication-{self.run_id}" /
                         self.architecture / "attempt.json").is_file())

    def _prepare_selected(self, version):
        profile_id = f"collection-publication-linux-{self.architecture}-18.6-{version}"
        profiles = json.loads((self.root / "support/verification-profiles.json").read_text())
        profiles["profiles"][profile_id] = {
            "scope": "publication", "platforms": [self.platform],
            "case_ids": ["collection-archive-suite"], "sources": ["profile-source.txt"],
        }
        (self.root / "support/verification-profiles.json").write_text(json.dumps(profiles))
        for path in self.publication.glob("current-receipt-*.json"):
            path.unlink()
        for path in self.records.glob("*.json"):
            path.unlink()
        attempt = json.loads((self.publication / "attempt.json").read_text())
        attempt["collection_versions"] = [version]
        attempt["source_sha256"] = {version: SOURCE_SHA256[version]}
        (self.publication / "attempt.json").write_text(json.dumps(attempt))
        manifest = {"component": "postgresql", "version": "18.6", "platform": "linux",
                    "architecture": self.architecture, "source_revision": self.revision,
                    "build_id": "fixture-build", "builder_inputs": {
                        "base_image": "ubuntu:22.04", "base_image_digest": "sha256:" + "a" * 64,
                        "packages_sha256": "b" * 64}}
        with tarfile.open(self.core_dir / self.core_name, "w:gz") as archive:
            data = json.dumps(manifest).encode()
            member = tarfile.TarInfo("postgresql/manifest.json")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        self.core_hash = self._sidecar(self.core_dir / self.core_name)
        report_path = self.collection_artifact / "static-analysis" / f"collection-{version}.json"
        report = json.loads(report_path.read_text())
        report["archives"] = [
            {"basename": self.core_name, "sha256": self.core_hash},
            {"basename": self.extension_names[version], "sha256": self.extension_hashes[version]},
        ]
        report_path.write_text(json.dumps(report))
        resolution = linux_core_resolution.create_record(
            self.core_dir / self.core_name, "18.6", self.architecture, "built",
            environ={"GITHUB_RUN_ID": self.run_id, "GITHUB_REPOSITORY": "example/repo",
                     "GITHUB_WORKFLOW_REF": "example/repo/.github/workflows/test.yml@refs/heads/test",
                     "GITHUB_SHA": self.revision, "GITHUB_RUN_ATTEMPT": "1"})
        (self.core_dir / "core-resolution.json").write_text(json.dumps(resolution))
        receipt_path = self.publication / f"current-receipt-{version}.json"
        receipt_creator.create(
            self.root, self.collection_artifact, self.core_dir, receipt_path, profile_id,
            "collection", version, "18.6", "18.6", self.architecture, "current",
            "6.8.0-test-kernel", "Alpine Linux", "3.22.6", self.image_id,
            "success", True, self.publication / "current-steps.json",
            environ={"GITHUB_SHA": self.revision, "GITHUB_RUN_ID": self.run_id,
                     "GITHUB_REPOSITORY": "example/repo", "GITHUB_SERVER_URL": "https://github.com"})
        emitter.emit(self.root, self.collection_artifact, self.core_dir, receipt_path, self.records)

    def test_selected_mode_retains_one_version_under_versioned_evidence_path(self):
        self._prepare_selected("1.1.1")
        retained = importer.import_run(self.root, self.core_artifact, self.collection_artifact,
                                       self.run_id, self.architecture, "18.6", "1.1.1")
        versioned = self.root / "support/evidence/collection-publication-456/x86_64/18.6/1.1.1"
        self.assertEqual({json.loads(path.read_text())["version"] for path in
                          (self.root / "support/verification").glob("*.json")}, {"1.1.1"})
        self.assertTrue((versioned / "core-resolution.json").is_file())
        self.assertIn(str((versioned / "current-receipt-1.1.1.json").relative_to(self.root)), retained)
        self.assertEqual(importer.import_run(self.root, self.core_artifact, self.collection_artifact,
                                             self.run_id, self.architecture, "18.6", "1.1.1"), retained)

    def test_selected_mode_rejects_core_provenance_digest_mismatch(self):
        self._prepare_selected("2.1.3")
        (self.core_dir / "postgresql-18.6-linux-x86_64.tar.gz").write_bytes(b"changed")
        self._sidecar(self.core_dir / "postgresql-18.6-linux-x86_64.tar.gz")
        with self.assertRaisesRegex(coverage.CoverageError, "invalid exact PostgreSQL core provenance"):
            importer.import_run(self.root, self.core_artifact, self.collection_artifact,
                                self.run_id, self.architecture, "18.6", "2.1.3")

    def test_selected_versions_share_run_without_evidence_path_collision(self):
        self._prepare_selected("1.1.1")
        importer.import_run(self.root, self.core_artifact, self.collection_artifact,
                            self.run_id, self.architecture, "18.6", "1.1.1")
        self._prepare_selected("2.1.3")
        importer.import_run(self.root, self.core_artifact, self.collection_artifact,
                            self.run_id, self.architecture, "18.6", "2.1.3")
        base = self.root / "support/evidence/collection-publication-456/x86_64/18.6"
        self.assertTrue((base / "1.1.1/current-receipt-1.1.1.json").is_file())
        self.assertTrue((base / "2.1.3/current-receipt-2.1.3.json").is_file())
        self.assertEqual({json.loads(path.read_text())["version"] for path in
                          (self.root / "support/verification").glob("*.json")}, set(VERSIONS))


if __name__ == "__main__":
    unittest.main()
