"""Tests for final-byte pg_cron macOS publication evidence."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from scripts.pg_cron.macos_target import SOURCE_SHA256, SOURCE_URL
import emit_pgcron_macos_publication as emitter

_DEFAULT_TARGET = object()


class PgCronMacOSFixture:
    def __init__(self, architecture="arm64", module_extension="dylib", pg_version="18.6"):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.core = self.base / "core"
        self.output = self.base / "output"
        for directory in (self.root, self.core, self.output):
            directory.mkdir()
        self.pg_version = pg_version
        self.version = "1.6.8"
        self.architecture = architecture
        self.module_path = f"lib/pg_cron.{module_extension}"
        self.platform = f"macos-{architecture}"
        self.profile_id = f"pgcron-publication-macos-{architecture}-{pg_version}"
        self.core_name = f"postgresql-{self.pg_version}-{self.platform}.tar.gz"
        self.extension_name = (f"pg_cron-{self.version}-postgresql-"
                               f"{self.pg_version}-{self.platform}.tar.gz")
        registry_path = Path("support/verification-profiles.json")
        registry = json.loads(registry_path.read_text())
        profile = registry["profiles"][self.profile_id]
        for relative in profile["sources"]:
            source = Path(relative)
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        shutil.copyfile("support.json", self.root / "support.json")
        shutil.copyfile("support/postgresql-releases.json",
                        self.root / "support/postgresql-releases.json")
        shutil.copyfile(registry_path, self.root / "support/verification-profiles.json")
        self.core_archive = self.core / self.core_name
        self.core_archive.write_bytes(b"fixture core bytes")
        self.core_digest = self.digest(self.core_archive)
        self.target_config = self.base / "target.json"
        self._write_resolved_target(self.core_digest)
        self.extension = self.output / self.extension_name
        self._archive_extension()
        self.environ = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "12345678901",
                        "GITHUB_REPOSITORY": "BernieSumption/pg_binaries",
                        "GITHUB_SERVER_URL": "https://github.com"}

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_resolved_target(self, digest):
        target = {
            "schema_version": 1,
            "profile_id": self.profile_id,
            "postgresql_version": self.pg_version,
            "pg_cron_version": self.version,
            "architecture": self.architecture,
            "platform": self.platform,
            "source": {"url": SOURCE_URL, "sha256": SOURCE_SHA256},
            "core_archive": {
                "basename": self.core_name,
                "run_id": "12345678901",
                "sha256": digest,
                "build_id": "github-12345678901-1",
                "source_revision": "b" * 40,
            },
        }
        self.target_config.write_text(json.dumps(target), encoding="utf-8")

    def _sidecar(self, path):
        path.with_name(path.name + ".sha256").write_text(
            f"{self.digest(path)}  {path.name}\n")

    def _archive_extension(self):
        metadata = {
            "project": "pg_cron", "version": self.version, "sql_names": ["pg_cron"],
            "requires": [],
            "configuration_prerequisites": [
                {"type": "postgresql_setting", "name": "shared_preload_libraries", "value": "pg_cron"},
                {"type": "postgresql_setting", "name": "cron.use_background_workers", "value": "on"},
            ],
            "runtime_prerequisites": [], "postgresql_version": self.pg_version,
            "platform": "macos", "architecture": self.architecture,
            "source": {"url": SOURCE_URL, "sha256": SOURCE_SHA256},
            "core_archive": {"basename": self.core_name, "sha256": self.core_digest},
        }
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "pg_cron"
            (package / "lib").mkdir(parents=True)
            (package / "share/extension").mkdir(parents=True)
            (package / "LICENSES/pg_cron").mkdir(parents=True)
            (package / self.module_path).write_bytes(b"Mach-O fixture")
            (package / "share/extension/pg_cron.control").write_text(
                "default_version = '1.6'\n")
            (package / "share/extension/pg_cron--1.0.sql").write_text("-- base DDL\n")
            (package / "share/extension/pg_cron--1.5--1.6.sql").write_text("-- update DDL\n")
            (package / "LICENSES/pg_cron/LICENCE").write_text(
                "See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md\n")
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
            "passed": True, "architecture": self.architecture, "findings": [],
            "inspected_files": ["bin/postgres"],
            "archives": [{"basename": name, "sha256": digest}
                         for name, digest in digests.items()],
        }))
        (self.output / "pg-cron-macho-inspection.json").write_text(json.dumps({
            "passed": True, "architecture": self.architecture, "file": self.module_path,
            "minimum_os": "11.0", "findings": [],
            "dependencies": {"@rpath/libpq.5.dylib": "lib/libpq.5.dylib"},
            "module_rpaths": ["@loader_path"], "archives": digests,
        }))
        (self.output / "probe-output.txt").write_text(
            "installation_relocated=true\njob_execution_mode=background_worker\n"
            "CREATE EXTENSION\nscheduled_job_status=succeeded\nscheduled_job_rows=1\n"
            " unschedule \n------------\n t\n(1 row)\n")

    def emit(self, cases=None, target_config=_DEFAULT_TARGET):
        if target_config is _DEFAULT_TARGET:
            target_config = self.target_config
        return emitter.emit(
            self.root, self.core, self.output, self.output,
            cases or {"archive-suite": "success", "static-analysis": "success"},
            "15.7.9", "macos15/20261018.1", target_config, environ=self.environ,
        )

    def close(self):
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

    def test_emits_for_both_macos_architectures(self):
        for architecture in ("arm64", "x86_64"):
            with self.subTest(architecture=architecture):
                fixture = PgCronMacOSFixture(architecture)
                try:
                    paths = fixture.emit()
                    record = json.loads(paths[-1].read_text())
                    self.assertEqual(record["platform"], f"macos-{architecture}")
                    self.assertEqual(record["assembled_core"]["sha256"], fixture.core_digest)
                finally:
                    fixture.close()

    def test_emits_and_binds_pgxs_so_module(self):
        fixture = PgCronMacOSFixture(module_extension="so")
        try:
            paths = fixture.emit()
            record = json.loads(paths[-1].read_text())
            self.assertEqual(record["outcome"], "passed")
            with tarfile.open(fixture.extension, "r:gz") as archive:
                self.assertIn("pg_cron/lib/pg_cron.so", archive.getnames())
            report = json.loads((fixture.output / "pg-cron-macho-inspection.json").read_text())
            self.assertEqual(report["file"], "lib/pg_cron.so")
        finally:
            fixture.close()

    def test_accepts_postgresql_15_versioned_bundled_libpq(self):
        fixture = PgCronMacOSFixture(pg_version="15.19")
        try:
            report_path = fixture.output / "pg-cron-macho-inspection.json"
            report = json.loads(report_path.read_text())
            report["dependencies"] = {"@rpath/libpq.5.15.dylib": "lib/libpq.5.15.dylib"}
            report_path.write_text(json.dumps(report))
            paths = fixture.emit()
            record = json.loads(paths[-1].read_text())
            self.assertEqual(record["postgresql_version"], "15.19")
        finally:
            fixture.close()

    def test_rejects_missing_or_mismatched_postgresql_15_libpq_resolution(self):
        for dependencies in ({}, {"@rpath/libpq.5.15.dylib": "lib/libpq.5.dylib"},
                             {"@rpath/libpq.6.15.dylib": "lib/libpq.6.15.dylib"}):
            with self.subTest(dependencies=dependencies):
                fixture = PgCronMacOSFixture(pg_version="15.19")
                try:
                    report_path = fixture.output / "pg-cron-macho-inspection.json"
                    report = json.loads(report_path.read_text())
                    report["dependencies"] = dependencies
                    report_path.write_text(json.dumps(report))
                    with self.assertRaisesRegex(Exception, "does not resolve bundled libpq"):
                        fixture.emit()
                finally:
                    fixture.close()

    def test_rejects_macho_report_for_different_module_suffix(self):
        fixture = PgCronMacOSFixture(module_extension="so")
        try:
            report_path = fixture.output / "pg-cron-macho-inspection.json"
            report = json.loads(report_path.read_text())
            report["file"] = "lib/pg_cron.dylib"
            report_path.write_text(json.dumps(report))
            with self.assertRaisesRegex(Exception, "Mach-O inspection"):
                fixture.emit()
        finally:
            fixture.close()

    def test_requires_target_config(self):
        with self.assertRaisesRegex(Exception, "resolved pg_cron target config is required"):
            self.fixture.emit(target_config=None)

    def test_uses_resolved_target_core_digest(self):
        changed = "c" * 64
        self.fixture._write_resolved_target(changed)
        with self.assertRaisesRegex(Exception, "checksum differs from the resolved target"):
            self.fixture.emit()

    def test_rejects_unresolved_target(self):
        value = json.loads(self.fixture.target_config.read_text())
        value["core_archive"] = {"basename": self.fixture.core_name}
        self.fixture.target_config.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "not been resolved"):
            self.fixture.emit()

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

    def test_rejects_extension_without_license_pointer(self):
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
            archive_path = base / "extension.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(package, arcname="pg_cron")
                metadata = base / "metadata.json"
                metadata.write_text(json.dumps({"project": "pg_cron"}))
                archive.add(metadata, arcname="metadata.json")
            with self.assertRaisesRegex(Exception, "LICENCE"):
                check_archive(archive_path)


if __name__ == "__main__":
    unittest.main()
