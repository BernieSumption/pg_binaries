import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).parents[1] / "tools/emit_pgaudit_macos_publication.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("emit_pgaudit_macos_publication", MODULE_PATH)
emitter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(emitter)


class EmitPgauditMacosPublicationTests(unittest.TestCase):
    def test_incomplete_attempt_is_retained_without_receipt(self):
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            output = directory / "output"
            paths = emitter.emit(
                root, directory / "core", directory / "extension", output,
                {"archive-suite": "failure", "symbols": "skipped", "diagnostics": "skipped"},
                "15.0", "macos-15/20261017", {
                    "GITHUB_SHA": "a" * 40,
                    "GITHUB_RUN_ID": "123456",
                    "GITHUB_REPOSITORY": "owner/repository",
                    "GITHUB_SERVER_URL": "https://github.com",
                },
            )
            self.assertEqual([path.name for path in paths], ["attempt.json"])
            attempt = json.loads(paths[0].read_text())
            self.assertEqual(attempt["steps"], {
                "archive-suite": "failure", "diagnostics": "skipped", "symbols": "skipped",
            })
            self.assertFalse((output / "publication/current-receipt.json").exists())

    def test_pg17_target_is_selected_without_mutating_emitter_defaults(self):
        root = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            paths = emitter.emit(
                root, Path(temporary) / "core", Path(temporary) / "extension", output,
                {"archive-suite": "failure", "symbols": "skipped", "diagnostics": "skipped"},
                "15.0", "macos-15/20261017", {
                    "GITHUB_SHA": "a" * 40,
                    "GITHUB_RUN_ID": "123456",
                    "GITHUB_REPOSITORY": "owner/repository",
                    "GITHUB_SERVER_URL": "https://github.com",
                }, pg_version="17.11",
            )
            attempt = json.loads(paths[0].read_text())
            self.assertEqual(attempt["profile_id"], "pgaudit-publication-macos-arm64-17.11")
            self.assertEqual(attempt["postgresql_version"], "17.11")
            self.assertEqual(attempt["pgaudit_version"], "17.1")
            self.assertIn("pgaudit-17.1-postgresql-17.11-macos-arm64.tar.gz",
                          attempt["archives_present"])
            self.assertFalse((output / "publication/current-receipt.json").exists())

    def test_archive_report_accepts_static_analysis_archive_list(self):
        emitter._archive_report({"archives": [
            {"basename": "postgresql-18.6-macos-arm64.tar.gz", "sha256": "a" * 64},
            {"basename": "pgaudit-18.0-postgresql-18.6-macos-arm64.tar.gz", "sha256": "b" * 64},
        ]}, {
            "postgresql-18.6-macos-arm64.tar.gz": "a" * 64,
            "pgaudit-18.0-postgresql-18.6-macos-arm64.tar.gz": "b" * 64,
        }, "static analysis")


if __name__ == "__main__":
    unittest.main()
