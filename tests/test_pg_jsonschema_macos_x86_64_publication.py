"""Tests for pg_jsonschema macOS x86_64 archive evidence and retention."""

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
import emit_pg_jsonschema_macos_x86_64_publication as emitter
import import_pg_jsonschema_macos_x86_64_publication as importer


class PublicationFixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.core = self.base / "core"
        self.output = self.base / "output"
        for directory in (self.root, self.core, self.output):
            directory.mkdir()
        (self.root / "support").mkdir()
        shutil.copyfile("support.json", self.root / "support.json")
        shutil.copyfile("support/verification-profiles.json", self.root / "support/verification-profiles.json")
        self.profile = {"scope": "publication", "platforms": [emitter.PLATFORM],
                        "case_ids": sorted(emitter.CASES), "sources_available": True,
                        "profile_revision": "a" * 64}
        self.profile_patch = patch.object(emitter.coverage, "verification_profile", return_value=self.profile)
        self.profile_patch.start()
        self.validation_patch = patch.object(emitter.coverage, "validate_verification_record")
        self.validation_patch.start()
        self.core_name = f"postgresql-{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz"
        self.extension_name = (f"pg_jsonschema-{emitter.EXTENSION_VERSION}-postgresql-"
                               f"{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz")
        self.core_archive = self.core / self.core_name
        self.core_archive.write_bytes(b"pinned core fixture")
        self.core_hash = self.digest(self.core_archive)
        self.core_hash_patch = patch.object(emitter, "CORE_SHA256", self.core_hash)
        self.core_hash_patch.start()
        self.core_build_patch = patch.object(emitter, "CORE_BUILD_ID", "github-123456789-1")
        self.core_build_patch.start()
        self.core_revision_patch = patch.object(emitter, "CORE_SOURCE_REVISION", "b" * 40)
        self.core_revision_patch.start()
        self.extension = self.output / self.extension_name
        self._archive()
        self.environ = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "12345678901",
                        "GITHUB_REPOSITORY": "example/pg_binaries", "GITHUB_SERVER_URL": "https://github.com"}

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def sidecar(self, path):
        path.with_name(path.name + ".sha256").write_text(f"{self.digest(path)}  {path.name}\n")

    def _archive(self):
        metadata = {"project": "pg_jsonschema", "version": emitter.EXTENSION_VERSION,
                    "sql_names": ["pg_jsonschema"], "requires": [],
                    "postgresql_version": emitter.PG_VERSION, "platform": "macos",
                    "architecture": "x86_64",
                    "source": {"url": emitter.SOURCE_URL, "commit": emitter.SOURCE_COMMIT,
                               "cargo_lock_sha256": emitter.CARGO_LOCK_SHA256},
                    "core_archive": {"basename": self.core_name, "sha256": self.core_hash},
                    "release_eligible": False, "release_blockers": emitter.RELEASE_BLOCKERS}
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            payload = base / "pg_jsonschema"
            (payload / "lib").mkdir(parents=True)
            (payload / "share/extension").mkdir(parents=True)
            (payload / "LICENSES").mkdir()
            (payload / "lib/pg_jsonschema.dylib").write_bytes(b"Mach-O fixture")
            (payload / "share/extension/pg_jsonschema.control").write_text("default_version = '0.3.4'\n")
            (payload / "LICENSES/pg_jsonschema.txt").write_text("PostgreSQL License\n")
            (payload / "LICENSES/pg_jsonschema-cargo-license-inventory.json").write_text("{}\n")
            (base / "metadata.json").write_text(json.dumps(metadata))
            with tarfile.open(self.extension, "w:gz") as archive:
                archive.add(payload, arcname="pg_jsonschema")
                archive.add(base / "metadata.json", arcname="metadata.json")
        self.sidecar(self.core_archive)
        self.sidecar(self.extension)
        digests = {self.core_name: self.digest(self.core_archive), self.extension_name: self.digest(self.extension)}
        (self.output / "static-analysis.json").write_text(json.dumps({
            "passed": True, "architecture": "x86_64", "inspected_files": [{"file": "lib/pg_jsonschema.dylib"}],
            "archives": digests,
        }))
        (self.output / "probe-output.txt").write_text("pg_jsonschema|0.3.4\n")
        (self.output / "build-evidence.txt").write_text(
            f"pg_jsonschema_source_commit={emitter.SOURCE_COMMIT}\n"
            f"cargo_lock_sha256={emitter.CARGO_LOCK_SHA256}\n"
            f"core_run_id={emitter.CORE_RUN_ID}\n"
            f"core_build_id={emitter.CORE_BUILD_ID}\n"
            f"core_source_revision={emitter.CORE_SOURCE_REVISION}\n"
            f"core_sha256={self.core_hash}\n")
        (self.output / "cargo-license-inventory.json").write_text("{}\n")

    def emit(self, step_results=None):
        return emitter.emit(self.root, self.core, self.output, self.output,
                            step_results or {"archive-suite": "success", "static-analysis": "success"},
                            "15.7.9", "macos15/20261017.1", self.environ)

    def close(self):
        self.validation_patch.stop()
        self.core_hash_patch.stop()
        self.core_build_patch.stop()
        self.core_revision_patch.stop()
        self.profile_patch.stop()
        self.temp.cleanup()


class PgJsonschemaMacOSPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PublicationFixture()
        self.addCleanup(self.fixture.close)

    def test_core_pin_matches_the_refreshed_current_intel_build(self):
        self.assertEqual(emitter.CORE_RUN_ID, "39093802497")
        pin = json.loads((Path(__file__).resolve().parents[1] /
                          "tools/pg_jsonschema_macos_pins/18.6-x86_64.json").read_text())
        self.assertEqual(pin["core_sha256"], "898256ad26f29cc055208ab443aff9ef9813bc5cbf150539b15dfce7e4ad017d")
        self.assertEqual(pin["core_build_id"], "github-39093802497-1")
        self.assertEqual(pin["core_source_revision"], "42082a506adfca1628c509f2c7b17037b9a12123")
        self.assertEqual(pin["status"], "current-profile-core-redistribution-pending")

    def test_emits_non_eligible_archive_bound_evidence(self):
        paths = self.fixture.emit()
        receipt = json.loads((self.fixture.output / "publication/current-receipt.json").read_text())
        record = json.loads(paths[-1].read_text())
        self.assertEqual(receipt["archives"][self.fixture.extension_name], self.fixture.digest(self.fixture.extension))
        self.assertFalse(receipt["release_eligible"])
        self.assertEqual(record["release_blockers"], emitter.RELEASE_BLOCKERS)
        self.assertEqual(record["assembled_core"]["sha256"], self.fixture.core_hash)

    def test_importer_retains_attempt_receipt_record_and_checksums(self):
        self.fixture.emit()
        with patch.object(importer.coverage, "verification_profile", return_value=self.fixture.profile), \
             patch.object(importer.coverage, "validate_verification_record"):
            paths = importer.import_run(self.fixture.root, self.fixture.core, self.fixture.output, "12345678901")
        self.assertTrue(any(path.endswith("current-receipt.json") for path in paths))
        self.assertTrue(any(path.endswith(".sha256") for path in paths))
        self.assertTrue(list((self.fixture.root / "support/verification").glob("*.json")))

    def test_failed_sql_probe_retains_raw_attempt_without_build_evidence(self):
        self.fixture.output.joinpath("build-evidence.txt").unlink()
        self.fixture.output.joinpath("probe-output.txt").write_text("partial SQL output\n")
        self.fixture.emit({"archive-suite": "failure", "static-analysis": "success"})
        with patch.object(importer.coverage, "verification_profile", return_value=self.fixture.profile):
            paths = importer.import_run(self.fixture.root, self.fixture.core, self.fixture.output, "12345678901")
        retained = self.fixture.root / paths[0]
        attempt = json.loads(retained.read_text())
        self.assertEqual(attempt["steps"]["archive-suite"], "failure")
        self.assertNotIn("build_evidence", attempt["reports"])
        self.assertTrue((self.fixture.root / paths[1]).is_file())
        self.assertFalse((self.fixture.output / "publication/current-receipt.json").exists())
        self.assertFalse(list((self.fixture.root / "support/verification").glob("*.json")))

    def test_failed_static_analysis_retains_attempt_without_static_report(self):
        self.fixture.output.joinpath("static-analysis.json").unlink()
        self.fixture.emit({"archive-suite": "success", "static-analysis": "failure"})
        with patch.object(importer.coverage, "verification_profile", return_value=self.fixture.profile):
            paths = importer.import_run(self.fixture.root, self.fixture.core, self.fixture.output, "12345678901")
        attempt = json.loads((self.fixture.root / paths[0]).read_text())
        self.assertEqual(attempt["steps"]["static-analysis"], "failure")
        self.assertNotIn("static_analysis", attempt["reports"])
        self.assertTrue(any(path.endswith("build-evidence.txt") for path in paths))
        self.assertFalse((self.fixture.output / "publication/current-receipt.json").exists())
        self.assertFalse(list((self.fixture.root / "support/verification").glob("*.json")))

    def test_rejects_unsafe_archive_member(self):
        malformed = self.fixture.output / "unsafe.tar.gz"
        with tarfile.open(self.fixture.extension, "r:gz") as source, tarfile.open(malformed, "w:gz") as target:
            for member in source.getmembers():
                target.addfile(member, source.extractfile(member) if member.isfile() else None)
            info = tarfile.TarInfo("../escape")
            info.size = 1
            target.addfile(info, io.BytesIO(b"x"))
        with self.assertRaises(emitter.coverage.CoverageError):
            emitter._metadata(malformed)


if __name__ == "__main__":
    unittest.main()
