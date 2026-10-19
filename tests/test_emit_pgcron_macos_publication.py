"""Tests for final-byte pg_cron macOS publication evidence."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import emit_pgcron_macos_publication as emitter


class PgCronMacOSFixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.core = self.base / "core"
        self.output = self.base / "output"
        for directory in (self.root, self.core, self.output):
            directory.mkdir()
        registry_path = Path("support/verification-profiles.json")
        registry = json.loads(registry_path.read_text())
        profile = registry["profiles"][emitter.PROFILE_ID]
        for relative in profile["sources"]:
            source = Path(relative)
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        shutil.copyfile("support.json", self.root / "support.json")
        shutil.copyfile("support/postgresql-releases.json",
                        self.root / "support/postgresql-releases.json")
        shutil.copyfile(registry_path, self.root / "support/verification-profiles.json")
        self.core_name = f"postgresql-{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz"
        self.extension_name = (f"pg_cron-{emitter.VERSION}-postgresql-"
                               f"{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz")
        self.core_archive = self.core / self.core_name
        self.core_archive.write_bytes(b"fixture core bytes")
        self.core_digest = self.digest(self.core_archive)
        self.target_config = self.base / "target.json"
        self.target_config.write_text(json.dumps({
            "schema_version": 1,
            "profile_id": emitter.PROFILE_ID,
            "postgresql_version": emitter.PG_VERSION,
            "pg_cron_version": emitter.VERSION,
            "architecture": emitter.ARCHITECTURE,
            "platform": emitter.PLATFORM,
            "source": {"url": emitter.SOURCE_URL, "sha256": emitter.SOURCE_SHA256},
            "core_archive": {
                "basename": self.core_name,
                "run_id": "12345678901",
                "sha256": self.core_digest,
                "build_id": "github-12345678901-1",
                "source_revision": "a" * 40,
            },
        }), encoding="utf-8")
        self.core_patch = patch.object(emitter, "CORE_SHA256", self.core_digest)
        self.core_patch.start()
        self.extension = self.output / self.extension_name
        self._archive_extension()
        self.environ = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "12345678901",
                        "GITHUB_REPOSITORY": "BernieSumption/pg_binaries",
                        "GITHUB_SERVER_URL": "https://github.com"}

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _sidecar(self, path):
        path.with_name(path.name + ".sha256").write_text(
            f"{self.digest(path)}  {path.name}\n")

    def _archive_extension(self):
        metadata = {
            "project": "pg_cron", "version": emitter.VERSION, "sql_names": ["pg_cron"],
            "requires": [],
            "configuration_prerequisites": [
                {"type": "postgresql_setting", "name": "shared_preload_libraries", "value": "pg_cron"},
                {"type": "postgresql_setting", "name": "cron.use_background_workers", "value": "on"},
            ],
            "runtime_prerequisites": [], "postgresql_version": emitter.PG_VERSION,
            "platform": "macos", "architecture": emitter.ARCHITECTURE,
            "source": {"url": emitter.SOURCE_URL, "sha256": emitter.SOURCE_SHA256},
            "core_archive": {"basename": self.core_name, "sha256": self.core_digest},
        }
        inventory = {"schema_version": 1, "components": [{
            "component": "pg_cron", "version": emitter.VERSION,
            "payload_paths": ["lib/pg_cron.dylib", "share/extension"],
            "license_file": "pg_cron.txt",
            "license_source": "https://github.com/citusdata/pg_cron/blob/v1.6.8/LICENSE",
            "source_url": emitter.SOURCE_URL, "source_sha256": emitter.SOURCE_SHA256,
            "redistribution_review": {
                "status": "resolved", "basis": "Fixture licence review.",
                "source_obligation": "none",
            },
        }]}
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "pg_cron"
            (package / "lib").mkdir(parents=True)
            (package / "share/extension").mkdir(parents=True)
            (package / "LICENSES").mkdir()
            (package / "lib/pg_cron.dylib").write_bytes(b"Mach-O fixture")
            (package / "share/extension/pg_cron.control").write_text(
                "default_version = '1.6'\n")
            (package / "LICENSES/pg_cron.txt").write_text("PostgreSQL License\n")
            (package / "LICENSES/pg_cron-inventory.json").write_text(json.dumps(inventory))
            metadata_path = Path(temporary) / "metadata.json"
            metadata_path.write_text(json.dumps(metadata))
            with tarfile.open(self.extension, "w:gz") as archive:
                archive.add(package, arcname="pg_cron")
                archive.add(metadata_path, arcname="metadata.json")
        self._sidecar(self.core_archive)
        self._sidecar(self.extension)
        digests = {self.core_name: self.core_digest,
                   self.extension_name: self.digest(self.extension)}
        (self.output / "static-analysis.json").write_text(json.dumps({
            "passed": True, "architecture": emitter.ARCHITECTURE, "findings": [],
            "inspected_files": ["bin/postgres"],
            "archives": [{"basename": name, "sha256": digest}
                         for name, digest in digests.items()],
        }))
        (self.output / "pg-cron-macho-inspection.json").write_text(json.dumps({
            "passed": True, "architecture": emitter.ARCHITECTURE, "file": "lib/pg_cron.dylib",
            "minimum_os": "11.0", "findings": [],
            "dependencies": {"@rpath/libpq.5.dylib": "lib/libpq.5.dylib"},
            "module_rpaths": ["@loader_path"], "archives": digests,
        }))
        (self.output / "probe-output.txt").write_text(
            "installation_relocated=true\njob_execution_mode=background_worker\n"
            "CREATE EXTENSION\nscheduled_job_status=succeeded\nscheduled_job_rows=1\n"
            " unschedule \n------------\n t\n(1 row)\n")

    def emit(self, cases=None, target_config=None):
        return emitter.emit(
            self.root, self.core, self.output, self.output,
            cases or {"archive-suite": "success", "static-analysis": "success"},
            "15.7.9", "macos15/20261018.1", self.environ,
            target_config=target_config,
        )

    def close(self):
        self.core_patch.stop()
        self.temp.cleanup()


class PgCronMacOSPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PgCronMacOSFixture()
        self.addCleanup(self.fixture.close)

    def test_emits_receipt_and_verification_record_bound_to_final_archives(self):
        paths = self.fixture.emit()
        receipt = json.loads((self.fixture.output / "publication/current-receipt.json").read_text())
        record = json.loads(paths[-1].read_text())
        self.assertEqual(receipt["archives"][self.fixture.core_name], self.fixture.core_digest)
        self.assertEqual(receipt["archives"][self.fixture.extension_name],
                         self.fixture.digest(self.fixture.extension))
        self.assertEqual(record["case_results"],
                         {"archive-suite": "passed", "static-analysis": "passed"})
        self.assertEqual(record["assembled_core"]["sha256"], self.fixture.core_digest)

    def test_resolved_target_supplies_checked_core_identity(self):
        with patch.object(emitter, "CORE_SHA256", "0" * 64):
            paths = self.fixture.emit(target_config=self.fixture.target_config)
        record = json.loads(paths[-1].read_text())
        self.assertEqual(record["assembled_core"]["sha256"], self.fixture.core_digest)

    def test_rejects_unresolved_target(self):
        value = json.loads(self.fixture.target_config.read_text())
        value["core_archive"] = {"basename": self.fixture.core_name}
        self.fixture.target_config.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "not been resolved"):
            self.fixture.emit(target_config=self.fixture.target_config)

    def test_incomplete_archives_retain_attempt_only(self):
        self.fixture.extension.unlink()
        paths = self.fixture.emit({"archive-suite": "failure", "static-analysis": "skipped"})
        self.assertEqual([path.name for path in paths], ["attempt.json"])
        self.assertFalse((self.fixture.output / "publication/current-receipt.json").exists())

    def test_rejects_bad_completed_job_evidence(self):
        probe = self.fixture.output / "probe-output.txt"
        probe.write_text(probe.read_text().replace("scheduled_job_status=succeeded",
                                                   "scheduled_job_status=failed"))
        with self.assertRaisesRegex(Exception, "completed background-worker job"):
            self.fixture.emit()

    def test_rejects_macho_report_for_different_archive_bytes(self):
        path = self.fixture.output / "pg-cron-macho-inspection.json"
        report = json.loads(path.read_text())
        report["archives"][self.fixture.extension_name] = "0" * 64
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(Exception, "Mach-O inspection"):
            self.fixture.emit()

    def test_rejects_extension_payload_without_licence_mapping(self):
        from check_macos_extension_license_inventory import check_archive

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            package = base / "pg_cron"
            (package / "share/extension").mkdir(parents=True)
            (package / "lib").mkdir()
            (package / "LICENSES").mkdir()
            (package / "share/extension/pg_cron.control").write_text(
                "default_version = '1.6'\n")
            (package / "lib/pg_cron.dylib").write_bytes(b"native fixture")
            (package / "LICENSES/pg_cron.txt").write_text("license\n")
            inventory = {"schema_version": 1, "components": [{
                "component": "pg_cron", "version": emitter.VERSION,
                "payload_paths": ["share/extension"], "license_file": "pg_cron.txt",
                "redistribution_review": {"status": "resolved", "basis": "Fixture.",
                                           "source_obligation": "none"},
            }]}
            (package / "LICENSES/pg_cron-inventory.json").write_text(json.dumps(inventory))
            archive_path = base / "extension.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(package, arcname="pg_cron")
                metadata = base / "metadata.json"
                metadata.write_text("{}")
                archive.add(metadata, arcname="metadata.json")
            with self.assertRaisesRegex(Exception, "unmapped native payload"):
                check_archive(archive_path)


if __name__ == "__main__":
    unittest.main()
