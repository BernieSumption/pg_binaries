"""Focused archive and candidate metadata checks for Windows hypopg."""

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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_hypopg_windows_archive as checker
import emit_hypopg_windows_publication as publication
import import_hypopg_windows_publication as importer
from test_create_windows_symbols import make_pe, make_pdb


class HypopgWindowsArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core = self.root / f"postgresql-18.6-{publication.PLATFORM}.tar.gz"
        self.extension = self.root / (
            f"hypopg-1.4.3-postgresql-18.6-{publication.PLATFORM}.tar.gz")

    def test_candidate_pins_current_core_identity(self):
        script = Path("scripts/hypopg/windows-feasibility.ps1").read_text()
        workflow = Path(".github/workflows/hypopg-windows-publication.yml").read_text()
        self.assertIn("windows_core_pin.py", script)
        self.assertIn("run-id: ${{ steps.core_pin.outputs.run_id }}", workflow)

    @staticmethod
    def _tar(path, entries):
        with tarfile.open(path, "w:gz") as archive:
            for name, content in entries:
                info = tarfile.TarInfo(name)
                if content is None:
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                    continue
                data = content.encode() if isinstance(content, str) else content
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))

    def _archives(self, release_eligible=False, unsafe=False, inventory=True):
        manifest = {
            "component": "postgresql", "version": "18.6", "postgresql_version": "18.6",
            "platform": "windows", "architecture": "x86_64", "build_id": publication.CORE_BUILD_ID,
            "source_revision": publication.CORE_SOURCE_REVISION,
        }
        self._tar(self.core, [("postgresql/manifest.json", json.dumps(manifest))])
        core_hash = hashlib.sha256(self.core.read_bytes()).hexdigest()
        metadata = {
            "project": "hypopg", "version": "1.4.3", "sql_names": ["hypopg"],
            "postgresql_version": "18.6", "platform": "windows", "architecture": "x86_64",
            "source": {"url": publication.SOURCE_URL, "sha256": publication.SOURCE_SHA256},
            "core_archive": {"basename": self.core.name, "sha256": core_hash},
            "release_eligible": release_eligible,
            "core_status": publication.CORE_STATUS,
        }
        prefix = "../escape" if unsafe else "hypopg"
        entries = [
            ("metadata.json", json.dumps(metadata)),
            (f"{prefix}/lib/hypopg.dll", make_pe()),
            ("hypopg/share/extension/hypopg.control", "default_version = '1.4.3'"),
            ("hypopg/share/extension/hypopg--1.4.3.sql", "SELECT 1;"),
            ("hypopg/LICENSES/", None),
            ("hypopg/LICENSES/HypoPG.txt", "MIT"),
        ]
        if inventory:
            entries.append(("hypopg/LICENSES/hypopg-inventory.json",
                            '{"schema_version":1,"source_files":[],"components":[{"component":"hypopg"}]}'))
        self._tar(self.extension, entries)
        (self.extension.parent / "hypopg.pdb").write_bytes(make_pdb())
        return core_hash

    def test_inspects_native_extension_and_current_profile_core_metadata(self):
        core_hash = self._archives()
        pe_report = self.root / "pe-report.json"
        extension_hash = hashlib.sha256(self.extension.read_bytes()).hexdigest()
        pe_report.write_text(json.dumps({
            "outcome": "passed", "inspected_files": ["lib/hypopg.dll"], "archives": [
                {"basename": self.core.name, "sha256": core_hash},
                {"basename": self.extension.name, "sha256": extension_hash},
            ],
        }))
        with patch.object(publication, "CORE_SHA256", core_hash):
            report = checker.inspect(self.core, self.extension, self.root / "report.json", pe_report)
        self.assertTrue(report["passed"])
        self.assertEqual(report["native_extension_files"], ["hypopg/lib/hypopg.dll"])
        self.assertIn("project-named-licence-inventory", report["checks"])
        self.assertEqual(report["pe_dependency_analysis_sha256"], hashlib.sha256(pe_report.read_bytes()).hexdigest())

    def test_rejects_pdb_identity_mismatch(self):
        core_hash = self._archives()
        pdb = self.root / "hypopg.pdb"
        data = bytearray(pdb.read_bytes())
        from test_create_windows_symbols import GUID
        offset = data.index(GUID)
        data[offset] ^= 1
        pdb.write_bytes(data)
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(RuntimeError, "GUID/age mismatch"):
                checker.inspect(self.core, self.extension, self.root / "report.json")
        self.assertFalse((self.root / "report.json").exists())

    def test_symbol_binding_changes_when_pdb_bytes_change(self):
        self._archives()
        pdb = self.root / "hypopg.pdb"
        original = checker.verify_symbols(self.extension, pdb)
        pdb.write_bytes(pdb.read_bytes() + b"changed")
        changed = checker.verify_symbols(self.extension, pdb)
        self.assertEqual(original["rsds_guid"], changed["rsds_guid"])
        self.assertNotEqual(original["pdb_sha256"], changed["pdb_sha256"])

    def test_rejects_pe_report_bound_to_different_archive(self):
        core_hash = self._archives()
        pe_report = self.root / "pe-report.json"
        pe_report.write_text(json.dumps({
            "outcome": "passed", "inspected_files": ["lib/hypopg.dll"],
            "archives": [{"basename": self.core.name, "sha256": core_hash},
                         {"basename": self.extension.name, "sha256": "0" * 64}],
        }))
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "exact core and extension archives"):
                checker.inspect(self.core, self.extension, self.root / "report.json", pe_report)

    def test_rejects_missing_project_license_inventory(self):
        core_hash = self._archives(inventory=False)
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "licence inventory"):
                checker.inspect(self.core, self.extension, self.root / "report.json")

    def test_rejects_release_eligible_extension_metadata(self):
        core_hash = self._archives(release_eligible=True)
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "metadata"):
                checker.inspect(self.core, self.extension, self.root / "report.json")

    def test_rejects_unsafe_archive_path_and_missing_inventory(self):
        core_hash = self._archives(unsafe=True)
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "unsafe path"):
                checker.inspect(self.core, self.extension, self.root / "report.json")

    def test_importer_refuses_symlinked_evidence_destination(self):
        source = self.root / "source.txt"
        source.write_text("evidence")
        repository = self.root / "repository"
        repository.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (repository / "support").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(Exception, "escapes repository root"):
            importer._copy([(source, repository / "support/evidence.txt")], repository)
        self.assertFalse((outside / "evidence.txt").exists())

    def test_importer_refuses_existing_symlink(self):
        source = self.root / "source.txt"
        source.write_text("evidence")
        destination = self.root / "destination.txt"
        destination.symlink_to(self.root / "missing.txt")
        with self.assertRaisesRegex(Exception, "refusing to replace"):
            importer._retain(source, destination, [])

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
        core_hash = self._archives(inventory=False)
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "licence inventory"):
                checker.inspect(self.core, self.extension, self.root / "report.json")

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
        (output / "probe-output.txt").write_text("Index Scan using hypothetical index\n")
        pe_report = output / "pe-dependency-analysis.json"
        pe_report.write_text(json.dumps({"outcome": "passed", "inspected_files": [
            "lib/hypopg.dll"], "archives": [
                {"basename": self.core.name, "sha256": core_hash},
                {"basename": self.extension.name, "sha256": extension_hash}]}))
        static = {
            "symbols": checker.verify_symbols(self.extension, output / "hypopg.pdb"),
            "passed": True, "architecture": publication.ARCHITECTURE,
            "archives": {self.core.name: core_hash, self.extension.name: extension_hash},
            "inspected_files": ["hypopg/lib/hypopg.dll"],
            "native_extension_files": ["hypopg/lib/hypopg.dll"],
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

        receipt_path = output / "publication/current-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["symbols"], static["symbols"])
        original_receipt = receipt_path.read_text()
        receipt["symbols"]["pdb_sha256"] = "0" * 64
        receipt_path.write_text(json.dumps(receipt))
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "receipt symbols differ"):
                importer.import_run(repo, core_dir, output, "123")
        receipt_path.write_text(original_receipt)
        pdb = output / "hypopg.pdb"
        pdb.write_bytes(pdb.read_bytes() + b"changed")
        with patch.object(publication, "CORE_SHA256", core_hash):
            with self.assertRaisesRegex(Exception, "receipt symbols differ"):
                importer.import_run(repo, core_dir, output, "123")

        record_name = ("hypopg-1.4.3-postgresql-18.6-windows-x86_64-current-123.json")
        retained = repo / "support/verification" / record_name
        self.assertTrue(retained.is_file())
        imported = [path.replace("\\", "/") for path in imported]
        self.assertIn(f"support/verification/{record_name}", imported)
        evidence_record = (repo / "support/evidence/hypopg-windows-publication-123/x86_64/"
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
            "hypopg_version": "1.4.3", "architecture": "x86_64",
            "release_eligible": False, "core_status": publication.CORE_STATUS,
            "steps": {"archive-suite": "success", "static-analysis": "success"},
        }))
        with self.assertRaisesRegex(Exception, "raw attempt identity"):
            importer.import_run(repo, self.root / "core", artifact, "123")


if __name__ == "__main__":
    unittest.main()
