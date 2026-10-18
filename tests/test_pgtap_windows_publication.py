"""Tests for final archive inspection and Windows pgTAP publication evidence."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_pgtap_windows_archive as checker
import emit_pgtap_windows_publication as publication
import import_pgtap_windows_publication as importer


class PgTapWindowsArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core = self.root / f"postgresql-18.6-{publication.PLATFORM}.tar.gz"
        self.extension = self.root / (
            f"pgtap-1.3.4-postgresql-18.6-{publication.PLATFORM}.tar.gz")
        self._make_core()
        self._make_extension()

    def test_candidate_pins_current_core_identity(self):
        script = Path("scripts/pgtap/windows-feasibility.ps1").read_text()
        workflow = Path(".github/workflows/pgtap-windows-publication.yml").read_text()
        self.assertIn("$runId = '39089826690'", script)
        self.assertIn(f"$coreSha256 = '{publication.CORE_SHA256}'", script)
        self.assertIn("source_revision = '01fe5d267c30f73bb6e44d2b37c18f008223bc75'", script)
        self.assertIn("run-id: 39089826690", workflow)

    def _tar(self, path, members):
        with tarfile.open(path, "w:gz") as archive:
            for name, payload in members:
                if payload is None:
                    info = tarfile.TarInfo(name)
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                    continue
                data = payload.encode()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, __import__("io").BytesIO(data))

    def _make_core(self):
        manifest = {
            "component": "postgresql", "version": "18.6", "postgresql_version": "18.6",
            "platform": "windows", "architecture": "x86_64", "build_id": "github-39089826690-1",
            "source_revision": "01fe5d267c30f73bb6e44d2b37c18f008223bc75",
        }
        self._tar(self.core, [("postgresql/manifest.json", json.dumps(manifest))])

    def _make_extension(self, extra=()):
        metadata = {
            "project": "pgtap", "version": "1.3.4", "sql_names": ["pgtap"],
            "postgresql_version": "18.6", "platform": "windows", "architecture": "x86_64",
            "source": {"url": publication.SOURCE_URL, "sha256": publication.SOURCE_SHA256},
            "core_archive": {"basename": self.core.name,
                             "sha256": getattr(self, "expected_digest", "0" * 64)},
        }
        self._tar(self.extension, [("metadata.json", json.dumps(metadata)),
                                   ("pgtap/share/extension/pgtap.control", "default_version = '1.3.4'"),
                                   *extra])

    def _with_pinned_core(self, callback):
        digest = hashlib.sha256(self.core.read_bytes()).hexdigest()
        self.expected_digest = digest
        with patch.object(publication, "CORE_SHA256", digest):
            metadata = {
                "project": "pgtap", "version": "1.3.4", "sql_names": ["pgtap"],
                "postgresql_version": "18.6", "platform": "windows", "architecture": "x86_64",
                "source": {"url": publication.SOURCE_URL, "sha256": publication.SOURCE_SHA256},
                "core_archive": {"basename": self.core.name, "sha256": digest},
            }
            self._tar(self.extension, [("pgtap", None), ("metadata.json", json.dumps(metadata)),
                                       ("pgtap/share/extension/pgtap.control", "default_version = '1.3.4'")])
            return callback(digest)

    def test_report_hashes_exact_archives_and_lists_checked_payload(self):
        def run(digest):
            report_path = self.root / "static-analysis.json"
            report = checker.inspect(self.core, self.extension, report_path)
            self.assertEqual(report["archives"][self.core.name], digest)
            self.assertEqual(report["native_extension_files"], [])
            self.assertIn("pgtap/share/extension/pgtap.control", report["inspected_files"])
            self.assertTrue(json.loads(report_path.read_text())["passed"])
        self._with_pinned_core(run)

    def test_rejects_native_code_in_sql_only_payload(self):
        def run(_digest):
            self._make_extension([("pgtap/bin/pgtap.dll", "native")])
            with self.assertRaisesRegex(Exception, "native code"):
                checker.inspect(self.core, self.extension, self.root / "report.json")
        self._with_pinned_core(run)

    def test_rejects_unsafe_archive_member(self):
        def run(_digest):
            self._make_extension([("../escape.sql", "unsafe")])
            with self.assertRaisesRegex(Exception, "unsafe path"):
                checker.inspect(self.core, self.extension, self.root / "report.json")
        self._with_pinned_core(run)

    def test_emits_and_imports_record_bound_to_final_archives(self):
        repo = self.root / "repo"
        (repo / "support").mkdir(parents=True)
        (repo / "support.json").write_bytes(Path("support.json").read_bytes())
        (repo / "support/verification-profiles.json").write_bytes(
            Path("support/verification-profiles.json").read_bytes())
        profile = json.loads((repo / "support/verification-profiles.json").read_text())[
            "profiles"][publication.PROFILE_ID]
        (repo / "support/postgresql-releases.json").parent.mkdir(exist_ok=True)
        shutil.copy("support/postgresql-releases.json", repo / "support/postgresql-releases.json")
        for source in profile["sources"]:
            source_path = Path(source)
            target = repo / source_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target)
        core_dir = self.root / "core-artifact"
        output = self.root / "pgtap-artifact"
        core_dir.mkdir()
        output.mkdir()
        core = core_dir / f"postgresql-18.6-{publication.PLATFORM}.tar.gz"
        manifest = {
            "component": "postgresql", "version": "18.6", "postgresql_version": "18.6",
            "platform": "windows", "architecture": "x86_64", "build_id": "github-39089826690-1",
            "source_revision": "01fe5d267c30f73bb6e44d2b37c18f008223bc75",
        }
        with tarfile.open(core, "w:gz") as archive:
            data = json.dumps(manifest).encode()
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        extension = output / (
            f"pgtap-1.3.4-postgresql-18.6-{publication.PLATFORM}.tar.gz")
        self.core = core
        digest = hashlib.sha256(core.read_bytes()).hexdigest()
        metadata = {
            "project": "pgtap", "version": "1.3.4", "sql_names": ["pgtap"],
            "postgresql_version": "18.6", "platform": "windows", "architecture": "x86_64",
            "source": {"url": publication.SOURCE_URL, "sha256": publication.SOURCE_SHA256},
            "core_archive": {"basename": core.name, "sha256": digest},
        }
        with tarfile.open(extension, "w:gz") as archive:
            for name, content in (
                ("metadata.json", json.dumps(metadata)),
                ("pgtap/share/extension/pgtap.control", "default_version = '1.3.4'"),
            ):
                data = content.encode()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        for path in (core, extension):
            hash_value = hashlib.sha256(path.read_bytes()).hexdigest()
            Path(str(path) + ".sha256").write_text(f"{hash_value}  {path.name}\n")
        output.joinpath("probe-output.txt").write_text("1..4\nok 1\nok 2\nok 3\nok 4\n")
        env = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "12345",
               "GITHUB_REPOSITORY": "owner/repo", "GITHUB_SERVER_URL": "https://github.com"}
        with patch.object(publication, "CORE_SHA256", digest):
            checker.inspect(core, extension, output / "static-analysis.json")
            paths = publication.emit(
                repo, core_dir, output, output,
                {"archive-suite": "success", "static-analysis": "success"},
                "10.0.20348", "windows-2022/image", env)
            retained = importer.import_run(repo, core_dir, output, "12345")
        self.assertEqual(len(paths), 3)
        self.assertTrue(any(path.endswith("pgtap-1.3.4-postgresql-18.6-windows-x86_64-current-12345.json")
                            for path in retained))
        record = json.loads((repo / "support/verification" /
                             "pgtap-1.3.4-postgresql-18.6-windows-x86_64-current-12345.json").read_text())
        self.assertEqual(record["assembled_core"]["sha256"], digest)
        static_path = output / "static-analysis.json"
        static_path.write_text(static_path.read_text() + " ")
        with patch.object(publication, "CORE_SHA256", digest):
            with self.assertRaisesRegex(Exception, "report hashes"):
                importer.import_run(repo, core_dir, output, "12345")


if __name__ == "__main__":
    unittest.main()
