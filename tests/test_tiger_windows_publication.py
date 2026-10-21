"""Focused checks for Windows TIGER publication evidence handling."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
import emit_tiger_windows_publication as emitter
import import_tiger_windows_publication as importer


class TigerWindowsPublicationTests(unittest.TestCase):
    def test_emitter_rejects_partial_target_archive_set(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            core, postgis, tiger = (root / name for name in ("core", "postgis", "tiger"))
            for directory in (core, postgis, tiger):
                directory.mkdir()
            (core / f"postgresql-18.6-{emitter.PLATFORM}.tar.gz").touch()
            with self.assertRaisesRegex(coverage.CoverageError, "incomplete archive set"):
                emitter.emit(root, core, postgis, tiger, root / "out",
                             {"archive-suite": "passed", "static-analysis": "passed"}, "Windows", "image")

    def test_emitter_rejects_missing_or_extra_step_results(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dirs = [root / name for name in ("core", "postgis", "tiger")]
            for directory in dirs:
                directory.mkdir()
            with self.assertRaisesRegex(coverage.CoverageError, "step results"):
                emitter.emit(root, *dirs, root / "out", {"archive-suite": "passed"}, "Windows", "image")

    def test_static_report_must_bind_all_three_archive_hashes(self):
        names = ["core.tar.gz", "postgis.tar.gz", "tiger.tar.gz"]
        hashes = {name: str(index) * 64 for index, name in enumerate(names, 1)}
        report = {"outcome": "passed", "architecture": "x86_64", "inspected_files": ["bin/postgres.exe"],
                  "archives": [{"basename": name, "sha256": hashes[name]} for name in names]}
        emitter.validate_static_report(report, names, hashes)
        report["archives"][1]["sha256"] = "0" * 64
        with self.assertRaisesRegex(coverage.CoverageError, "exact archives"):
            emitter.validate_static_report(report, names, hashes)

    def test_importer_rejects_non_numeric_run_id_before_reading_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dirs = [root / name for name in ("core", "postgis", "tiger")]
            for directory in dirs:
                directory.mkdir()
            with self.assertRaisesRegex(coverage.CoverageError, "numeric"):
                importer.import_run(root, *dirs, "run-123")

    def test_workflow_emits_receipt_after_relocated_archive_verification(self):
        workflow = Path(".github/workflows/tiger-windows-selected-publication.yml").read_text()
        verifier = workflow.index("windows-verify-publication.ps1")
        emitter_call = workflow.index("emit_tiger_windows_publication.py")
        artifact = workflow.index("${{ runner.temp }}/bundle/tiger/publication/**")
        self.assertLess(verifier, emitter_call)
        self.assertLess(emitter_call, artifact)
        self.assertIn("static-analysis.json", workflow)
        self.assertIn("probe-output.txt", workflow)
        self.assertIn("identity.json", workflow)


if __name__ == "__main__":
    unittest.main()
