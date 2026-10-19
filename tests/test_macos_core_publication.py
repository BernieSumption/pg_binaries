import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


emitter = load("emit_macos_core_publication")
importer = load("import_macos_core_publication")


class MacOSCorePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "support").mkdir()
        (self.root / "support.json").write_text("{}")
        self.archives = self.root / "archives"
        self.verification = self.root / "verification"
        self.output = self.verification
        self.archives.mkdir()
        self.verification.mkdir()
        self.version, self.architecture, self.run_id = "18.6", "arm64", "31415"
        self.revision = "a" * 40
        self.archive_name = f"postgresql-{self.version}-macos-{self.architecture}.tar.gz"
        self.archive = self.archives / self.archive_name
        self.archive.write_bytes(b"final archive bytes")
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        Path(str(self.archive) + ".sha256").write_text(f"{digest}  {self.archive_name}\n")
        self.digests = {self.archive_name: digest}
        self.profile = {"profile_id": f"postgresql-publication-macos-{self.architecture}-{self.version}",
                        "scope": "publication", "platforms": [f"macos-{self.architecture}"],
                        "case_ids": sorted(emitter.CASES), "profile_revision": "b" * 64,
                        "compatible_profile_revisions": ["b" * 64], "sources_available": True}
        self.steps = {case: "success" for case in self.profile["case_ids"]}
        self.steps_path = self.root / "steps.json"
        self.steps_path.write_text(json.dumps(self.steps))
        self.static = self._report("static-analysis.json", {"passed": True, "inspected_files": ["postgresql/bin/postgres"],
                                                             "archives": [{"basename": self.archive_name,
                                                                           "sha256": digest}]})
        self.symbols = self._report("debug-symbols/index.json", {"schema_version": 1, "files": [
            {"archive": self.archive_name, "archive_sha256": digest,
             "module_path": "postgresql/bin/postgres", "dsym_path": "dSYMs/postgres.dSYM",
             "dsym_sha256": "c" * 64}]})
        self.diagnostics = self._report("diagnostics.json", {
            "platform": "macos", "architecture": self.architecture,
            "postgresql_version": self.version, "postgresql_failure": {"kind": "server-error"},
            "archives": self.digests})
        self.environ = {"GITHUB_RUN_ID": self.run_id, "GITHUB_REPOSITORY": "owner/repo",
                        "GITHUB_SERVER_URL": "https://github.com"}

    def tearDown(self):
        self.temp.cleanup()

    def _report(self, name, value):
        path = self.verification / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def _emit(self, steps=None):
        return emitter.emit(self.root, self.archives, self.output, self.version, self.architecture,
                            self.revision, "15.0", "macos-15-runner", self.steps_path,
                            self.static, self.symbols, self.diagnostics,
                            {**self.environ, "GITHUB_SHA": self.revision})

    def test_emitter_and_importer_bind_record_to_final_archive_bytes(self):
        with mock.patch.object(emitter, "_profile", return_value=self.profile), \
                mock.patch.object(emitter.coverage, "validate_verification_record") as validate:
            emitted = self._emit()
        self.assertEqual(len(emitted), 2)
        validate.assert_called_once()
        record = json.loads(emitted[1].read_text())
        self.assertEqual(record["sha256"], self.digests[self.archive_name])
        with mock.patch.object(importer.publication, "_profile", return_value=self.profile), \
                mock.patch.object(importer.coverage, "validate_verification_record") as validate:
            retained = importer.import_run(self.root, self.archives, self.verification,
                                           self.run_id, self.version, self.architecture)
        validate.assert_called_once()
        self.assertTrue(any(path.endswith("debug-symbols-index.json") for path in retained))
        self.assertTrue((self.root / "support/verification" / Path(emitted[1]).name).is_file())

    def test_failed_attempt_is_retained_without_record_or_archive(self):
        self.archive.unlink()
        raw = {case: "failure" if case == "archive-suite" else "skipped" for case in self.steps}
        self.steps_path.write_text(json.dumps(raw))
        with mock.patch.object(emitter, "_profile", return_value=self.profile):
            emitted = self._emit()
        self.assertEqual([path.name for path in emitted], ["publication-attempt.json"])
        with mock.patch.object(importer.publication, "_profile", return_value=self.profile):
            retained = importer.import_run(self.root, self.archives, self.verification,
                                           self.run_id, self.version, self.architecture)
        self.assertEqual(len(retained), 2)
        self.assertTrue((self.root / retained[0]).is_file())

    def test_emitter_requires_registered_version_architecture_profile(self):
        with mock.patch.object(emitter.coverage, "verification_profile",
                               side_effect=emitter.coverage.CoverageError("unknown")):
            with self.assertRaisesRegex(emitter.coverage.CoverageError, "registered target profile"):
                emitter._profile(ROOT, self.version, self.architecture)


if __name__ == "__main__":
    unittest.main()
