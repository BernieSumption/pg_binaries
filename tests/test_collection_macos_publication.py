import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
import emit_collection_macos_publication as emitter
import import_collection_macos_publication as importer


REPO = Path(__file__).resolve().parents[1]
VERSIONS = emitter.VERSIONS


class CollectionMacosPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "repo"
        (self.root / "support").mkdir(parents=True)
        shutil.copy(REPO / "support.json", self.root / "support.json")
        shutil.copy(REPO / "support/postgresql-releases.json", self.root / "support/postgresql-releases.json")
        self.core_dir = self.base / "core"
        self.output = self.base / "collection"
        self.publication = self.output / "publication"
        self.records = self.publication / "records"
        self.core_dir.mkdir()
        self.output.mkdir()
        self.run_id = "7654321"
        self.revision = "a" * 40
        self.image_id = "macos-15/20261018.1"
        self.environ = {"GITHUB_SHA": self.revision, "GITHUB_RUN_ID": self.run_id,
                        "GITHUB_REPOSITORY": "example/repo", "GITHUB_SERVER_URL": "https://github.com"}
        self._configure_architecture("arm64")

    def tearDown(self):
        self.temporary.cleanup()

    def _configure_architecture(self, architecture):
        if hasattr(self, "architecture") and self.architecture != architecture:
            shutil.rmtree(self.output)
            self.output.mkdir()
        self.architecture = architecture
        self.pg_version = "18.6"
        self.platform = f"macos-{architecture}"
        self.profile_id = f"collection-publication-macos-{architecture}-18.6"
        base_target = json.loads((REPO / f"tools/collection_macos_targets/18.6-{architecture}.json").read_text())
        core_bytes = f"test core archive {architecture}".encode()
        self.core_hash = hashlib.sha256(core_bytes).hexdigest()
        core_name = base_target["core_archive"]["basename"]
        self.core = self.core_dir / core_name
        self.core.write_bytes(core_bytes)
        self.core.with_name(self.core.name + ".sha256").write_text(f"{self.core_hash}  {self.core.name}\n")
        base_target["core_archive"].update({"sha256": self.core_hash, "run_id": "123456",
                                            "build_id": "github-123456-1", "source_revision": "b" * 40})
        self.target_config = self.base / f"target-{architecture}.json"
        self.target_config.write_text(json.dumps(base_target))
        (self.root / "support/verification-profiles.json").write_text(json.dumps({
            "schema_version": 1, "profiles": {self.profile_id: {
                "scope": "publication", "platforms": [self.platform],
                "case_ids": sorted(emitter.CASES), "sources": ["profile-source.txt"]}}}))
        (self.root / "profile-source.txt").write_text("profile source\n")
        module_file = "lib/collection.so" if self.pg_version.startswith("15.") else "lib/collection.dylib"
        self.extension_hashes = {}
        for version, source_hash in VERSIONS.items():
            name = f"collection-{version}-postgresql-{self.pg_version}-{self.platform}.tar.gz"
            path = self.output / name
            metadata = {"project": "collection", "version": version,
                        "sql_names": ["collection"], "requires": [],
                        "configuration_prerequisites": [], "runtime_prerequisites": [],
                        "postgresql_version": self.pg_version, "platform": "macos",
                        "architecture": architecture,
                        "source": {"url": f"https://github.com/aws/pgcollection/archive/refs/tags/v{version}.tar.gz",
                                   "sha256": source_hash},
                        "core_archive": {"basename": core_name, "sha256": self.core_hash}}
            with tarfile.open(path, "w:gz") as archive:
                self._add(archive, "metadata.json", json.dumps(metadata).encode())
                self._add(archive, "collection/" + module_file, b"native fixture")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n")
            self.extension_hashes[version] = digest
            (self.output / f"static-analysis-collection-{version}.json").write_text(json.dumps({
                "passed": True, "architecture": architecture,
                "inspected_files": [{"file": module_file}],
                "archives": [{"basename": core_name, "sha256": self.core_hash},
                             {"basename": path.name, "sha256": digest}]}))

    @staticmethod
    def _add(archive, name, data):
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))

    def _emit(self, steps=None):
        return emitter.emit(self.root, self.core_dir, self.output, self.output,
                            steps or {"archive-suite": "success", "static-analysis": "success"},
                            "15.0", self.image_id, self.target_config, self.environ)

    def _import(self):
        return importer.import_run(self.root, self.core_dir, self.output, self.run_id, self.target_config)

    def test_emits_and_imports_both_architectures_and_two_records(self):
        for architecture in ("arm64", "x86_64"):
            with self.subTest(architecture=architecture):
                self._configure_architecture(architecture)
                self._emit()
                retained = self._import()
                self.assertEqual(len([p for p in retained if p.startswith("support/verification/")]), 2)
                for path in (self.root / "support/verification").glob("*.json"):
                    record = json.loads(path.read_text())
                    if record["platform"] != self.platform:
                        continue
                    self.assertEqual(record["assembled_core"]["sha256"], self.core_hash)
                    self.assertEqual(record["release_eligibility"], "blocked-pending-dependency-review")
                    coverage.validate_verification_record(record, coverage.load_json(self.root / "support.json"), self.root)
                self.assertEqual(self._import(), retained)

    def test_existing_workflows_keep_their_pinned_target_until_retired(self):
        identity = {"sha256": self.core_hash, "run_id": "123456",
                    "build_id": "github-123456-1", "source_revision": "b" * 40}
        with patch.object(emitter.collection_macos_identity, "selected_identity",
                          return_value=(self.pg_version, self.architecture, identity)):
            emitter.emit(self.root, self.core_dir, self.output, self.output,
                         {"archive-suite": "success", "static-analysis": "success"},
                         "15.0", self.image_id, environ=self.environ)
            retained = importer.import_run(self.root, self.core_dir, self.output, self.run_id)
        self.assertEqual(len([path for path in retained if path.startswith("support/verification/")]), 2)

    def test_emitter_and_importer_reject_target_archive_identity_mismatch(self):
        changed = json.loads(self.target_config.read_text())
        changed["core_archive"]["sha256"] = "0" * 64
        self.target_config.write_text(json.dumps(changed))
        with self.assertRaisesRegex(coverage.CoverageError, "differs from the resolved target"):
            self._emit()
        with self.assertRaisesRegex(coverage.CoverageError, "differs from resolved target"):
            self._import()

    def test_emitter_and_importer_require_resolved_target(self):
        unresolved = json.loads(self.target_config.read_text())
        unresolved["core_archive"] = {"basename": unresolved["core_archive"]["basename"]}
        self.target_config.write_text(json.dumps(unresolved))
        with self.assertRaisesRegex(ValueError, "requires a resolved core identity"):
            self._emit()
        with self.assertRaisesRegex(ValueError, "requires a resolved core identity"):
            self._import()

    def test_import_rejects_receipt_hash_that_differs_from_final_archive(self):
        self._emit()
        receipt_path = self.publication / "current-receipt-1.1.1.json"
        receipt = json.loads(receipt_path.read_text())
        extension = next(name for name in receipt["archives"] if name.startswith("collection-"))
        receipt["archives"][extension] = "0" * 64
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(coverage.CoverageError, "receipt identity or hashes"):
            self._import()

    def test_retains_raw_failed_attempt_when_no_archive_bytes_exist(self):
        self.core.unlink()
        self._emit({"archive-suite": "failure", "static-analysis": "skipped"})
        retained = self._import()
        self.assertEqual(len(retained), 3)
        attempt = json.loads((self.root / retained[0]).read_text())
        self.assertEqual(attempt["steps"], {"archive-suite": "failure", "static-analysis": "skipped"})

    def test_writes_raw_attempt_before_profile_validation_failure(self):
        profile_path = self.root / "support/verification-profiles.json"
        profiles = json.loads(profile_path.read_text())
        profiles["profiles"][self.profile_id]["sources"] = ["support.json", "profile-source.txt"]
        profile_path.write_text(json.dumps(profiles))
        with self.assertRaisesRegex(coverage.CoverageError, "sources must be sorted"):
            self._emit()
        attempt = json.loads((self.publication / "attempt.json").read_text())
        self.assertEqual(attempt["source_revision"], self.revision)


if __name__ == "__main__":
    unittest.main()
