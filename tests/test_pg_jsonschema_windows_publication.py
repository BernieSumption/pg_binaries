"""Focused archive and candidate metadata checks for Windows pg_jsonschema."""

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
import check_pg_jsonschema_windows_archive as checker
import emit_pg_jsonschema_windows_publication as publication
import import_pg_jsonschema_windows_publication as importer
import windows_core_target
from license_pointer import LICENSE_POINTER


class PgJsonschemaWindowsArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core = self.root / f"postgresql-18.6-{publication.PLATFORM}.tar.gz"
        self.extension = self.root / (
            f"pg_jsonschema-0.3.4-postgresql-18.6-{publication.PLATFORM}.tar.gz")

    def test_windows_builder_uses_pointer_and_retains_build_identity_checks(self):
        script = Path("scripts/pg_jsonschema/windows-feasibility.ps1").read_text()
        self.assertIn("configuration_prerequisites = @(); runtime_prerequisites = @()", script)
        self.assertIn("tools/license_pointer.py') write $payload pg_jsonschema", script)
        self.assertIn("tools/license_pointer.py') verify $extensionArchive pg_jsonschema", script)
        for obsolete in ("inventory_cargo_licenses.py", "create_pg_jsonschema_component_inventory.py",
                         "check_pg_jsonschema_component_inventory.py", "cargo metadata", "$upstreamLicense"):
            self.assertNotIn(obsolete, script)
        for required in ("$extensionCommit", "$cargoLockSha256", "$actualLockSha256",
                         "cargo_lock_sha256=$actualLockSha256", "cargo pgrx install",
                         "probe.sql", "check_pe_dependencies.py"):
            self.assertIn(required, script)

    def test_metadata_validation_uses_selected_core_target(self):
        target = publication.load_core_identity("17.11")
        metadata = {
            "project": "pg_jsonschema", "version": "0.3.4", "sql_names": ["pg_jsonschema"],
            "postgresql_version": "17.11", "platform": "windows", "architecture": "x86_64",
            "source": {"url": publication.SOURCE_URL, "commit": publication.SOURCE_COMMIT,
                       "cargo_lock_sha256": publication.CARGO_LOCK_SHA256},
            "core_archive": {"basename": "postgresql-17.11-windows-x86_64.tar.gz",
                             "sha256": target["sha256"]},
            "release_eligible": False, "core_status": target["status"],
        }
        path = self.root / "selected-metadata.tar.gz"
        self._tar(path, [("metadata.json", json.dumps(metadata))])
        publication._metadata(path, "17.11", target)
        metadata["postgresql_version"] = "18.6"
        self._tar(path, [("metadata.json", json.dumps(metadata))])
        with self.assertRaisesRegex(Exception, "pinned publication target"):
            publication._metadata(path, "17.11", target)

    @staticmethod
    def _tar(path, entries):
        with tarfile.open(path, "w:gz") as archive:
            for name, content in entries:
                info = tarfile.TarInfo(name)
                if content is None:
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                    continue
                data = content.encode()
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))

    def _archives(self, release_eligible=False, unsafe=False, pointer=True, core_pointer=True):
        manifest = {
            "component": "postgresql", "version": "18.6", "postgresql_version": "18.6",
            "platform": "windows", "architecture": "x86_64", "build_id": publication.CORE_BUILD_ID,
            "source_revision": publication.CORE_SOURCE_REVISION,
        }
        core_entries = [("postgresql/manifest.json", json.dumps(manifest))]
        if core_pointer:
            core_entries.append(("postgresql/LICENSES/postgresql/LICENCE", LICENSE_POINTER))
        self._tar(self.core, core_entries)
        core_hash = hashlib.sha256(self.core.read_bytes()).hexdigest()
        metadata = {
            "project": "pg_jsonschema", "version": "0.3.4", "sql_names": ["pg_jsonschema"],
            "postgresql_version": "18.6", "platform": "windows", "architecture": "x86_64",
            "source": {"url": publication.SOURCE_URL, "commit": publication.SOURCE_COMMIT,
                       "cargo_lock_sha256": publication.CARGO_LOCK_SHA256},
            "core_archive": {"basename": self.core.name, "sha256": core_hash},
            "release_eligible": release_eligible,
            "core_status": publication.CORE_STATUS,
        }
        prefix = "../escape" if unsafe else "pg_jsonschema"
        entries = [
            ("metadata.json", json.dumps(metadata)),
            (f"{prefix}/lib/pg_jsonschema.dll", "MZ-test-binary"),
            ("pg_jsonschema/share/extension/pg_jsonschema.control", "default_version = '0.3.4'"),
            ("pg_jsonschema/share/extension/pg_jsonschema--0.3.4.sql", "SELECT 1;"),
        ]
        if pointer:
            entries.append(("pg_jsonschema/LICENSES/pg_jsonschema/LICENCE", LICENSE_POINTER))
        self._tar(self.extension, entries)
        return core_hash

    def test_inspects_native_extension_and_current_profile_core_metadata(self):
        core_hash = self._archives()
        pe_report = self.root / "pe-report.json"
        extension_hash = hashlib.sha256(self.extension.read_bytes()).hexdigest()
        pe_report.write_text(json.dumps({
            "outcome": "passed", "inspected_files": ["lib/pg_jsonschema.dll"], "archives": [
                {"basename": self.core.name, "sha256": core_hash},
                {"basename": self.extension.name, "sha256": extension_hash},
            ],
        }))
        with patch.object(publication, "CORE_SHA256", core_hash):
            report = checker.inspect(self.core, self.extension, self.root / "report.json", pe_report)
        self.assertTrue(report["passed"])
        self.assertEqual(report["native_extension_files"], ["pg_jsonschema/lib/pg_jsonschema.dll"])
        self.assertIn("core-and-component-licence-pointers", report["checks"])
        self.assertEqual(report["pe_dependency_analysis_sha256"], hashlib.sha256(pe_report.read_bytes()).hexdigest())

    def test_rejects_release_eligible_extension_metadata(self):
        core_hash = self._archives(release_eligible=True)
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "metadata"):
                checker.inspect(self.core, self.extension, self.root / "report.json")

    def test_rejects_unsafe_archive_path(self):
        core_hash = self._archives(unsafe=True)
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "unsafe path"):
                checker.inspect(self.core, self.extension, self.root / "report.json")

    def test_rejects_missing_core_license_pointer(self):
        core_hash = self._archives(core_pointer=False)
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "PostgreSQL licence pointer"):
                checker.inspect(self.core, self.extension, self.root / "report.json")

    def test_emit_does_not_require_a_separate_current_core_profile_record(self):
        repo = self.root / "repo"
        for relative in ("support.json", "support/verification-profiles.json",
                         "support/postgresql-releases.json"):
            destination = repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(relative, destination)
        profiles = json.loads((repo / "support/verification-profiles.json").read_text())["profiles"]
        for relative in profiles[publication.PROFILE_ID]["sources"]:
            destination = repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(relative, destination)
        output = self.root / "output"
        paths = publication.emit(
            repo, self.root / "core", self.root / "archives", output,
            {"archive-suite": "success", "static-analysis": "success"},
            "10.0.20348.0", "windows-2022/test-image",
            {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123",
             "GITHUB_REPOSITORY": "owner/repo", "GITHUB_SERVER_URL": "https://github.com"})
        attempt = output / "publication/attempt.json"
        self.assertTrue(attempt.is_file())
        self.assertEqual(json.loads(attempt.read_text())["run_id"], "123")
        self.assertEqual(paths, [attempt])
        core_hash = self._archives(pointer=False)
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "licence pointer"):
                checker.inspect(self.core, self.extension, self.root / "report.json")

    def test_selected_profiles_emit_and_import_incomplete_attempts(self):
        for index, version in enumerate(("15.19", "16.15", "17.11", "18.6"), start=1):
            repo = self.root / version
            profile_id = f"pg-jsonschema-publication-windows-x86_64-{version}"
            for relative in ("support.json", "support/verification-profiles.json",
                             "support/postgresql-releases.json"):
                destination = repo / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(relative, destination)
            profiles = json.loads((repo / "support/verification-profiles.json").read_text())["profiles"]
            for relative in profiles[profile_id]["sources"]:
                source, destination = Path(relative), repo / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)

            core_dir, archives, output = repo / "core", repo / "archives", repo / "output"
            core_dir.mkdir()
            archives.mkdir()
            if index == 1:
                (core_dir / f"postgresql-{version}-{publication.PLATFORM}.tar.gz").write_bytes(b"partial core")
            identity_path = repo / f"core-target-{version}.json"
            windows_core_target.write_target(version, identity_path, repo)
            paths = publication.emit(
                repo, core_dir, archives, output,
                {"archive-suite": "failure", "static-analysis": "skipped"},
                "10.0.20348.0", "windows-2022/test-image",
                {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": str(100 + index),
                 "GITHUB_REPOSITORY": "owner/repo", "GITHUB_SERVER_URL": "https://github.com"},
                postgresql_version=version, core_identity_path=identity_path)
            attempt = json.loads((output / "publication/attempt.json").read_text())
            self.assertEqual(attempt["profile_id"], profile_id)
            self.assertEqual(attempt["postgresql_version"], version)
            self.assertIs(attempt["core_identity_known"], False)
            self.assertEqual(paths, [output / "publication/attempt.json"])
            imported = importer.import_run(repo, core_dir, output, str(100 + index), version, identity_path)
            retained = repo / "support/evidence" / f"pg_jsonschema-windows-publication-{100 + index}/x86_64/attempt.json"
            self.assertTrue(retained.is_file())
            self.assertIn(str(retained.relative_to(repo)), imported)

    def test_static_target_cannot_stand_in_for_full_identity_when_both_archives_exist(self):
        repo = self.root / "repo"
        for relative in ("support.json", "support/verification-profiles.json",
                         "support/postgresql-releases.json"):
            destination = repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(relative, destination)
        profiles = json.loads((repo / "support/verification-profiles.json").read_text())["profiles"]
        for relative in profiles[publication.PROFILE_ID]["sources"]:
            destination = repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(relative, destination)
        core_dir, archives = self.root / "core", self.root / "archives"
        core_dir.mkdir()
        archives.mkdir()
        identity_path = self.root / "static-target.json"
        windows_core_target.write_target("18.6", identity_path)
        (core_dir / self.core.name).write_bytes(b"core")
        (archives / self.extension.name).write_bytes(b"extension")
        with self.assertRaisesRegex(Exception, "identity pin"):
            publication.emit(
                repo, core_dir, archives, self.root / "output",
                {"archive-suite": "failure", "static-analysis": "skipped"},
                "10.0.20348.0", "windows-2022/test-image",
                {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123",
                 "GITHUB_REPOSITORY": "owner/repo", "GITHUB_SERVER_URL": "https://github.com"},
                core_identity_path=identity_path)

    def test_importer_persists_validated_record_to_verification_directory(self):
        repo = self.root / "repo"
        for relative in ("support.json", "support/verification-profiles.json",
                         "support/postgresql-releases.json"):
            destination = repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(relative, destination)
        profiles = json.loads((repo / "support/verification-profiles.json").read_text())["profiles"]
        for relative in profiles[publication.PROFILE_ID]["sources"]:
            destination = repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(relative, destination)

        core_dir, output = self.root / "core", self.root / "output"
        core_dir.mkdir()
        output.mkdir()
        self.core = core_dir / self.core.name
        self.extension = output / self.extension.name
        core_hash = self._archives()
        extension_hash = hashlib.sha256(self.extension.read_bytes()).hexdigest()
        for archive, digest in ((self.core, core_hash), (self.extension, extension_hash)):
            Path(str(archive) + ".sha256").write_text(f"{digest}  {archive.name}\n")
        (output / "probe-output.txt").parent.mkdir(parents=True, exist_ok=True)
        (output / "probe-output.txt").write_text("CREATE EXTENSION pg_jsonschema\n")
        (output / "first-run-probe-output.txt").write_text("CREATE EXTENSION pg_jsonschema\n")
        pe_report = output / "pe-dependency-analysis.json"
        pe_report.write_text(json.dumps({"outcome": "passed", "inspected_files": [
            "lib/pg_jsonschema.dll"], "archives": [
                {"basename": self.core.name, "sha256": core_hash},
                {"basename": self.extension.name, "sha256": extension_hash},
            ]}))
        static = {
            "passed": True, "architecture": publication.ARCHITECTURE,
            "archives": {self.core.name: core_hash, self.extension.name: extension_hash},
            "inspected_files": ["pg_jsonschema/lib/pg_jsonschema.dll"],
            "native_extension_files": ["pg_jsonschema/lib/pg_jsonschema.dll"],
            "pe_dependency_analysis_sha256": hashlib.sha256(pe_report.read_bytes()).hexdigest(),
        }
        (output / "static-analysis.json").write_text(json.dumps(static))

        with patch.object(publication, "CORE_SHA256", core_hash):
            publication.emit(
                repo, core_dir, output, output,
                {"archive-suite": "success", "static-analysis": "success"},
                "10.0.20348.0", "windows-2022/test-image",
                {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123",
                 "GITHUB_REPOSITORY": "owner/repo", "GITHUB_SERVER_URL": "https://github.com"})
            imported = importer.import_run(repo, core_dir, output, "123")

        record_name = ("pg_jsonschema-0.3.4-postgresql-18.6-windows-x86_64-current-123.json")
        retained = repo / "support/verification" / record_name
        self.assertTrue(retained.is_file())
        imported = [path.replace("\\", "/") for path in imported]
        self.assertIn(f"support/verification/{record_name}", imported)
        evidence_record = (repo / "support/evidence/pg_jsonschema-windows-publication-123/x86_64/"
                          / "verification-record.json")
        self.assertEqual(retained.read_bytes(), evidence_record.read_bytes())
        record = json.loads(retained.read_text())
        coverage_module = sys.modules.get("coverage")
        if coverage_module is None:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
            import coverage as coverage_module
        self.assertTrue(coverage_module.validate_verification_record(
            record, coverage_module.load_json(repo / "support.json"), repo))

    def test_importer_rejects_attempt_for_a_different_run(self):
        repo = self.root / "repo"
        (repo / "support").mkdir(parents=True)
        for relative in ("support.json", "support/verification-profiles.json",
                         "support/postgresql-releases.json"):
            destination = repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(Path(relative).read_bytes())
        profile = json.loads((repo / "support/verification-profiles.json").read_text())[
            "profiles"][publication.PROFILE_ID]
        for relative in profile["sources"]:
            source, destination = Path(relative), repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        artifact = self.root / "artifact"
        pub = artifact / "publication"
        pub.mkdir(parents=True)
        (pub / "attempt.json").write_text(json.dumps({
            "schema_version": 1, "run_id": "999", "source_revision": "a" * 40,
            "profile_id": publication.PROFILE_ID, "postgresql_version": "18.6",
            "pg_jsonschema_version": "0.3.4", "architecture": "x86_64",
            "release_eligible": False, "core_status": publication.CORE_STATUS,
            "steps": {"archive-suite": "success", "static-analysis": "success"},
        }))
        with self.assertRaisesRegex(Exception, "raw attempt identity"):
            importer.import_run(repo, self.root / "core", artifact, "123")


if __name__ == "__main__":
    unittest.main()
