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


class CollectionMacosPublicationTests(unittest.TestCase):
    def test_unresolved_postgresql_17_identity_is_rejected(self):
        import collection_macos_identity
        pin_root = self.base / "pins"
        pin_file = pin_root / "tools/collection_macos_pins/17.11-arm64.json"
        pin_file.parent.mkdir(parents=True)
        pin_file.write_text(json.dumps({
            "run_id": "test-run", "sha256": None, "build_id": None,
            "source_revision": None}))
        with patch.object(collection_macos_identity, "ROOT", pin_root):
            with self.assertRaisesRegex(ValueError, "identity is incomplete"):
                collection_macos_identity.selected_identity("17.11", "arm64")

    def test_registered_profile_has_valid_source_revision(self):
        profile = coverage.verification_profile(REPO, emitter.PROFILE_ID)
        self.assertEqual(profile["case_ids"], sorted(emitter.CASES))
        registry = json.loads((REPO / "support/verification-profiles.json").read_text())
        sources = registry["profiles"][emitter.PROFILE_ID]["sources"]
        pin_source = f"tools/collection_macos_pins/{emitter.PG_VERSION}-{emitter.ARCHITECTURE}.json"
        self.assertIn(pin_source, sources)
        for version in ("17.11", "18.6"):
            for architecture in ("arm64", "x86_64"):
                candidate = f"tools/collection_macos_pins/{version}-{architecture}.json"
                self.assertEqual(candidate in sources, candidate == pin_source)
        workflow = next(source for source in sources if source.startswith(".github/workflows/collection-macos-")
                        and source.endswith("-publication.yml"))
        self.assertIn(f"run-id: {emitter.CORE_IDENTITY['run_id']}", (REPO / workflow).read_text())

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "repo"
        (self.root / "support").mkdir(parents=True)
        shutil.copy(REPO / "support.json", self.root / "support.json")
        shutil.copy(REPO / "support/postgresql-releases.json", self.root / "support/postgresql-releases.json")
        source_file = self.root / "profile-source.txt"
        source_file.write_text("profile source\n")
        (self.root / "support/verification-profiles.json").write_text(json.dumps({
            "schema_version": 1, "profiles": {emitter.PROFILE_ID: {
                "scope": "publication", "platforms": [emitter.PLATFORM],
                "case_ids": sorted(emitter.CASES), "sources": ["profile-source.txt"]}}}))
        self.core_dir = self.base / "core"
        self.output = self.base / "collection"
        self.publication = self.output / "publication"
        self.records = self.publication / "records"
        self.core_dir.mkdir()
        self.output.mkdir()
        self.run_id = "7654321"
        self.revision = "a" * 40
        self.image_id = "macos-15/20261018.1"
        self.core = self.core_dir / emitter.CORE_NAME
        self.core.write_bytes(b"test core archive")
        self.core_hash = hashlib.sha256(self.core.read_bytes()).hexdigest()
        self.core.with_name(self.core.name + ".sha256").write_text(f"{self.core_hash}  {self.core.name}\n")
        self.old_core_sha = emitter.CORE_SHA256
        emitter.CORE_SHA256 = self.core_hash
        self.extension_hashes = {}
        for version, source_hash in emitter.VERSIONS.items():
            name = f"collection-{version}-postgresql-{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz"
            path = self.output / name
            metadata = {"project": "collection", "version": version,
                        "sql_names": ["collection"], "requires": [],
                        "configuration_prerequisites": [], "runtime_prerequisites": [],
                        "postgresql_version": emitter.PG_VERSION, "platform": "macos",
                        "architecture": emitter.ARCHITECTURE,
                        "source": {"url": f"https://github.com/aws/pgcollection/archive/refs/tags/v{version}.tar.gz",
                                   "sha256": source_hash},
                        "core_archive": {"basename": emitter.CORE_NAME, "sha256": self.core_hash}}
            with tarfile.open(path, "w:gz") as archive:
                self._add(archive, "metadata.json", json.dumps(metadata).encode())
                self._add(archive, "collection/lib/collection.dylib", b"native fixture")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n")
            self.extension_hashes[version] = digest
            (self.output / f"static-analysis-collection-{version}.json").write_text(json.dumps({
                "passed": True, "architecture": emitter.ARCHITECTURE,
                "inspected_files": [{"file": "lib/collection.dylib"}],
                "archives": [{"basename": emitter.CORE_NAME, "sha256": self.core_hash},
                             {"basename": path.name, "sha256": digest}]}))
        self.environ = {"GITHUB_SHA": self.revision, "GITHUB_RUN_ID": self.run_id,
                        "GITHUB_REPOSITORY": "example/repo", "GITHUB_SERVER_URL": "https://github.com"}

    def tearDown(self):
        emitter.CORE_SHA256 = self.old_core_sha
        self.temporary.cleanup()

    @staticmethod
    def _add(archive, name, data):
        member = tarfile.TarInfo(name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))

    def _emit(self, steps=None):
        return emitter.emit(self.root, self.core_dir, self.output, self.output,
                            steps or {"archive-suite": "success", "static-analysis": "success"},
                            "15.0", self.image_id, self.environ)

    def _import(self):
        return importer.import_run(self.root, self.core_dir, self.output, self.run_id)

    def test_emits_and_imports_two_final_archive_bound_records(self):
        self._emit()
        retained = self._import()
        self.assertEqual(len([p for p in retained if p.startswith("support/verification/")]), 2)
        for path in (self.root / "support/verification").glob("*.json"):
            record = json.loads(path.read_text())
            self.assertEqual(record["assembled_core"]["sha256"], self.core_hash)
            self.assertEqual(record["release_eligibility"], "blocked-pending-dependency-review")
            coverage.validate_verification_record(record, coverage.load_json(self.root / "support.json"), self.root)
        self.assertEqual(self._import(), retained)

    def test_import_rejects_receipt_hash_that_differs_from_final_archive(self):
        self._emit()
        receipt_path = self.publication / "current-receipt-1.1.1.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["archives"][next(name for name in receipt["archives"] if name.startswith("collection-"))] = "0" * 64
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(coverage.CoverageError, "receipt identity or hashes"):
            self._import()

    def test_retains_raw_failed_attempt_when_no_archive_bytes_exist(self):
        (self.core_dir / emitter.CORE_NAME).unlink()
        self._emit({"archive-suite": "failure", "static-analysis": "skipped"})
        retained = self._import()
        self.assertEqual(len(retained), 3)
        attempt = json.loads((self.root / retained[0]).read_text())
        self.assertEqual(attempt["steps"], {"archive-suite": "failure", "static-analysis": "skipped"})

    def test_writes_raw_attempt_before_profile_validation_failure(self):
        profile_path = self.root / "support/verification-profiles.json"
        profiles = json.loads(profile_path.read_text())
        profiles["profiles"][emitter.PROFILE_ID]["sources"] = ["support.json", "profile-source.txt"]
        profile_path.write_text(json.dumps(profiles))
        with self.assertRaisesRegex(coverage.CoverageError, "sources must be sorted"):
            self._emit()
        attempt = json.loads((self.publication / "attempt.json").read_text())
        self.assertEqual(attempt["source_revision"], self.revision)


if __name__ == "__main__":
    unittest.main()
