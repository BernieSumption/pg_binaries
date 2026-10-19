import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import linux_extension_candidate as candidate


class LinuxExtensionCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.pg, self.version = "17.11", "1.4.3"
        self.platform = "linux-x86_64"
        self.core_name = f"postgresql-{self.pg}-{self.platform}.tar.gz"
        self.extension_name = f"hypopg-{self.version}-postgresql-{self.pg}-{self.platform}.tar.gz"
        self.core = self.directory / self.core_name
        self.extension = self.directory / self.extension_name
        core_manifest = json.dumps({"component": "postgresql", "version": self.pg,
                                    "platform": "linux", "architecture": "x86_64"}).encode()
        with tarfile.open(self.core, "w:gz") as archive:
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(core_manifest)
            archive.addfile(info, io.BytesIO(core_manifest))
        payload = {"schema_version": 1, "component": "hypopg", "target": {},
                   "upstream_sources": {}, "dependencies": {},
                   "build_configuration": {}, "recipes": {}}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False).encode()
        self.identity = {**payload, "sha256": hashlib.sha256(canonical).hexdigest()}
        self._write_extension({"project": "hypopg", "version": self.version,
                               "platform": "linux", "architecture": "x86_64",
                               "postgresql_version": self.pg,
                               "build_inputs": self.identity})
        self.record_name = f"hypopg-{self.version}-postgresql-{self.pg}-{self.platform}-current-42.json"
        self.record_path = self.directory / self.record_name
        self.source = {"run_id": "42", "run_attempt": 1, "head_sha": "b" * 40,
                       "repository": "owner/repo"}
        self.record = {
            "schema_version": 2, "scope": "publication", "profile_id": "test",
            "profile_revision": "c" * 64, "test_cases": ["probe"],
            "case_results": {"probe": "passed"}, "outcome": "passed",
            "component": "hypopg", "project": "HypoPG", "version": self.version,
            "postgresql_version": self.pg, "platform": self.platform,
            "environment": {"endpoint": "current"},
            "ci": {"provider": "github-actions", "run_id": "42",
                   "run_url": "https://github.com/owner/repo/actions/runs/42",
                   "source_revision": "b" * 40, "build_revision": "b" * 40,
                   "test_revision": "b" * 40},
            "sha256": hashlib.sha256(self.extension.read_bytes()).hexdigest(),
            "assembled_core": {"archive": self.core_name, "version": self.pg,
                               "sha256": hashlib.sha256(self.core.read_bytes()).hexdigest()},
        }
        self._write_record()
        self.manifest = {"schema_version": 1,
                         "target": {"postgresql_version": self.pg, "platform": self.platform},
                         "source": self.source,
                         "files": {self.core_name: str(self.core),
                                   self.core_name + ".sha256": str(self._sidecar(self.core)),
                                   self.extension_name: str(self.extension),
                                   self.extension_name + ".sha256": str(self._sidecar(self.extension)),
                                   self.record_name: str(self.record_path)},
                         "sha256": {}, "extension_record": self.record_name}
        self._hash_manifest_files()

    def tearDown(self):
        self.temp.cleanup()

    def _write_extension(self, metadata):
        content = json.dumps(metadata).encode()
        with tarfile.open(self.extension, "w:gz") as archive:
            info = tarfile.TarInfo("metadata.json")
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))

    def _sidecar(self, archive):
        path = archive.with_name(archive.name + ".sha256")
        path.write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
        return path

    def _write_record(self):
        self.record["sha256"] = hashlib.sha256(self.extension.read_bytes()).hexdigest()
        self.record["assembled_core"]["sha256"] = hashlib.sha256(self.core.read_bytes()).hexdigest()
        self.record_path.write_text(json.dumps(self.record))

    def _hash_manifest_files(self):
        self.manifest["sha256"] = {
            name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for name, path in self.manifest["files"].items()}

    def validate(self):
        return candidate.validate_candidate(
            self.manifest, root=ROOT, core_name=self.core_name,
            extension_name=self.extension_name, core_component="postgresql",
            core_version=self.pg, extension_component="hypopg",
            extension_version=self.version, extension_project="hypopg",
            extension_display_name="HypoPG", expected_build_inputs=self.identity)

    def test_validates_candidate_without_claiming_core_verification(self):
        with mock.patch.object(candidate.coverage, "load_json", return_value={}), \
                mock.patch.object(candidate.coverage, "validate_verification_record", return_value=True):
            result = self.validate()
        self.assertEqual(len(result["verification_records"]), 1)
        self.assertEqual(result["verification_records"][0]["component"], "hypopg")
        self.assertNotIn("core_verification_record", result)

    def test_rejects_sidecar_archive_record_and_assembled_core_mismatches(self):
        with mock.patch.object(candidate.coverage, "load_json", return_value={}), \
                mock.patch.object(candidate.coverage, "validate_verification_record", return_value=True):
            sidecar = Path(self.manifest["files"][self.extension_name + ".sha256"])
            sidecar.write_text("0" * 64 + "  " + self.extension_name)
            self._hash_manifest_files()
            with self.assertRaisesRegex(candidate.CandidateError, "sidecar"):
                self.validate()
            self._sidecar(self.extension)
            self._hash_manifest_files()
            self.record["assembled_core"]["sha256"] = "0" * 64
            self.record_path.write_text(json.dumps(self.record))
            self._hash_manifest_files()
            with self.assertRaisesRegex(candidate.CandidateError, "assembled_core"):
                self.validate()

    def test_rejects_wrong_ci_producer_and_stale_build_identity(self):
        with mock.patch.object(candidate.coverage, "load_json", return_value={}), \
                mock.patch.object(candidate.coverage, "validate_verification_record", return_value=True):
            self.record["ci"]["run_id"] = "99"
            self._write_record()
            self._hash_manifest_files()
            with self.assertRaisesRegex(candidate.CandidateError, "CI identity"):
                self.validate()
            self.record["ci"]["run_id"] = "42"
            self._write_record()
            self._write_extension({"project": "hypopg", "version": self.version,
                                   "platform": "linux", "architecture": "x86_64",
                                   "postgresql_version": self.pg,
                                   "build_inputs": {"schema_version": 1}})
            self._sidecar(self.extension)
            self._write_record()
            self._hash_manifest_files()
            with self.assertRaisesRegex(candidate.CandidateError, "build inputs differ"):
                self.validate()

    def test_rejects_missing_manifest_schema_and_wrong_selected_core(self):
        with mock.patch.object(candidate.coverage, "load_json", return_value={}), \
                mock.patch.object(candidate.coverage, "validate_verification_record", return_value=True):
            del self.manifest["schema_version"]
            with self.assertRaisesRegex(candidate.CandidateError, "unsupported schema"):
                self.validate()
            self.manifest["schema_version"] = 1
            with self.assertRaisesRegex(candidate.CandidateError, "core version differs"):
                candidate.validate_candidate(
                    self.manifest, root=ROOT, core_name=self.core_name,
                    extension_name=self.extension_name, core_component="postgresql",
                    core_version="18.6", extension_component="hypopg",
                    extension_version=self.version, extension_project="hypopg",
                    extension_display_name="HypoPG", expected_build_inputs=self.identity)


if __name__ == "__main__":
    unittest.main()
