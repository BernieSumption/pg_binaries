"""Tests for archive-bound Windows pg_cron publication evidence."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import emit_pgcron_windows_publication as emitter
import import_pgcron_windows_publication as importer


class Fixture:
    def __init__(self, pg_version="18.6"):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.pg_version = pg_version
        self.root = self.base / "repo"
        self.archives = self.base / "archives"
        self.output = self.base / "output"
        for path in (self.root, self.archives, self.output):
            path.mkdir()
        self.sources = [
            ".github/workflows/pgcron-windows-selected-publication.yml",
            "scripts/pg_cron/verify-windows.ps1", "scripts/pg_cron/windows-build.ps1",
            "support.json", "support/postgresql-releases.json",
            "tests/test_pgcron_windows_publication.py", "tools/coverage.py",
            "tools/check_pe_dependencies.py", "tools/create_windows_symbols.py",
            "tools/emit_pgcron_windows_publication.py",
            "tools/import_pgcron_windows_publication.py", "tools/stage_windows_core_symbols.py",
            "tools/windows_core_pin.py",
            f"support/windows-core-pins/{pg_version}-x86_64.json",
        ]
        for relative in self.sources:
            source, destination = ROOT / relative, self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        registry = json.loads((ROOT / "support/verification-profiles.json").read_text())
        registry["profiles"][emitter.PROFILE_ID.format(pg_version)] = {
            "scope": "publication", "platforms": ["windows-x86_64"],
            "case_ids": emitter.CASES, "sources": sorted(self.sources),
        }
        (self.root / "support").mkdir(exist_ok=True)
        (self.root / "support/verification-profiles.json").write_text(json.dumps(registry))
        (self.root / "support/verification").mkdir()
        self.core_name = f"postgresql-{pg_version}-windows-x86_64.tar.gz"
        self.extension_name = f"pg_cron-1.6.8-postgresql-{pg_version}-windows-x86_64.tar.gz"
        self.core = self.archives / self.core_name
        self.extension = self.archives / self.extension_name
        self._write_archives()
        self.digests = {path.name: self.digest(path) for path in (self.core, self.extension)}
        for path in (self.core, self.extension):
            path.with_name(path.name + ".sha256").write_text(f"{self.digest(path)}  {path.name}\n")
        self.report_dir = self.output
        (self.report_dir / "probe-output.txt").write_text(
            "CREATE EXTENSION\ninstallation_relocated=true\njob_status=succeeded\njob_rows=1\n")
        (self.report_dir / "static-analysis.json").write_text(json.dumps({
            "outcome": "passed", "platform": "windows", "architecture": "x86_64",
            "inspected_files": ["bin/postgres.exe"],
            "archives": [{"basename": name, "sha256": digest} for name, digest in self.digests.items()],
        }))
        (self.report_dir / "debug-symbols").mkdir()
        (self.report_dir / "debug-symbols/index.json").write_text(json.dumps({
            "files": [{"archive": name, "archive_sha256": digest} for name, digest in self.digests.items()],
        }))
        shutil.copyfile(self.report_dir / "debug-symbols/index.json",
                        self.report_dir / "debug-symbols-index.json")
        self.results = {case: "passed" for case in emitter.CASES}
        self.environ = {"GITHUB_RUN_ID": "12345678901", "GITHUB_REPOSITORY": "BernieSumption/pg_binaries",
                        "GITHUB_SERVER_URL": "https://github.com"}

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_archives(self):
        core = self.base / "core"
        (core / "postgresql").mkdir(parents=True)
        (core / "postgresql/manifest.json").write_text(json.dumps({
            "component": "postgresql", "version": self.pg_version, "platform": "windows",
            "architecture": "x86_64", "build_id": "github-11111111111-1",
            "source_revision": "b" * 40,
        }))
        with tarfile.open(self.core, "w:gz") as archive:
            archive.add(core / "postgresql/manifest.json", arcname="postgresql/manifest.json")
        metadata = self.base / "metadata.json"
        metadata.write_text(json.dumps({
            "project": "pg_cron", "version": "1.6.8", "postgresql_version": self.pg_version,
            "platform": "windows", "architecture": "x86_64",
            "build_id": "github-22222222222-2", "source_revision": "c" * 40,
            "core_archive": {"basename": self.core_name, "sha256": self.digest(self.core)},
        }))
        with tarfile.open(self.extension, "w:gz") as archive:
            archive.add(metadata, arcname="metadata.json")

    def emit(self, step_results=None):
        return emitter.emit(self.root, self.archives, self.output,
                            {"static-analysis": self.output / "static-analysis.json",
                             "symbols": self.output / "debug-symbols/index.json",
                             "archive-suite": self.output / "probe-output.txt"},
                            step_results or self.results, "a" * 40, "10.0.20348.2402",
                            "windows-2022-image", environ=self.environ, pg_version=self.pg_version)

    def close(self):
        self.temp.cleanup()


class PgCronWindowsPublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)

    def test_emits_and_imports_record_bound_to_final_archives(self):
        self.fixture.emit()
        retained = importer.import_run(self.fixture.root, self.fixture.archives,
                                       self.fixture.output, "12345678901")
        self.assertTrue(any(path.startswith("support/verification/") for path in retained))
        evidence = self.fixture.root / "support/evidence/pgcron-windows-publication-12345678901"
        self.assertEqual(json.loads((evidence / "publication-receipt.json").read_text())["archives"],
                         self.fixture.digests)

    def test_rejects_report_for_different_archive_bytes(self):
        self.fixture.emit()
        report = self.fixture.output / "static-analysis.json"
        value = json.loads(report.read_text())
        value["archives"][0]["sha256"] = "0" * 64
        report.write_text(json.dumps(value))
        with self.assertRaisesRegex(Exception, "final archive bytes"):
            importer.import_run(self.fixture.root, self.fixture.archives,
                                self.fixture.output, "12345678901")

    def test_incomplete_attempt_is_retained_without_passing_record(self):
        self.fixture.extension.unlink()
        self.fixture.emit({"archive-suite": "failed", "static-analysis": "skipped", "symbols": "skipped"})
        retained = importer.import_run(self.fixture.root, self.fixture.archives,
                                       self.fixture.output, "12345678901")
        self.assertTrue(any(path.endswith("publication-attempt.json") for path in retained))
        self.assertEqual(list((self.fixture.root / "support/verification").glob("*.json")), [])

    def test_all_checked_postgresql_versions_use_distinct_archive_identities(self):
        for pg_version in emitter.PG_VERSIONS:
            fixture = Fixture(pg_version)
            try:
                fixture.emit()
                record = next(fixture.output.glob("pg_cron-*-current-*.json"))
                value = json.loads(record.read_text())
                self.assertEqual(value["postgresql_version"], pg_version)
                self.assertEqual(value["assembled_core"]["archive"],
                                 f"postgresql-{pg_version}-windows-x86_64.tar.gz")
            finally:
                fixture.close()


if __name__ == "__main__":
    unittest.main()
