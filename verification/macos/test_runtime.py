from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from verification.runtime import archive_contents, clean_disposable, extension_probe_session, record_versions, verify


class RuntimeChecksTests(unittest.TestCase):
    def test_archive_controls_must_match_declared_extension_names(self):
        file = SimpleNamespace(kind="file", mode=0o755)
        core = {f"postgresql/bin/{name}": file for name in ("initdb", "pg_ctl", "psql", "pg_dump", "pg_restore")}
        for controls, expected in ((["vector", "unexpected"], "unexpected"), ([], "missing")):
            entries = {f"postgresql/share/extension/{name}.control": file for name in controls}
            with self.subTest(controls=controls), patch("verification.runtime.read_archive", side_effect=[core, entries]):
                with self.assertRaisesRegex(RuntimeError, expected):
                    archive_contents(Path("postgresql.tar.gz"), {"pgvector": Path("vector.tar.gz")})

    def test_probe_records_the_installed_sql_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("verification.runtime.run", side_effect=["", '{"vector":"sql-version-different-from-release"}']) as run:
                versions = extension_probe_session(["pgvector"], root, ["psql"], {}, root / "server.log")
            self.assertEqual(versions, {"vector": "sql-version-different-from-release"})
            self.assertIn("pg_extension", run.call_args.args[0][-1])
            self.assertIn("CASCADE", (root / "extension-probes.sql").read_text())

    def test_versions_must_match_records_and_other_combinations(self):
        report = {"postgresql_version": None, "extension_versions": {}}
        checks = [{"name": "PostgreSQL version", "outcome": "passed", "version": "18.6"},
                  {"name": "SQL probes", "outcome": "passed", "extension_versions": {"vector": "0.8.7"}}]
        with self.assertRaisesRegex(RuntimeError, "build record"):
            record_versions(report, checks, {"vector"}, "18.5")
        record_versions(report, checks, {"vector"}, "18.6")
        checks[1]["extension_versions"]["vector"] = "0.8.8"
        with self.assertRaisesRegex(RuntimeError, "differs between combinations"):
            record_versions(report, checks, {"vector"}, "18.6")

    def test_unsafe_archive_stops_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "invalid.tar.gz"
            archive.write_bytes(b"invalid archive")
            output = root / "output"
            checks = verify(archive, {}, output)
            self.assertEqual(checks[0]["outcome"], "failed")
            self.assertEqual(checks[1]["outcome"], "not_run")
            self.assertFalse(output.exists())

    def test_cleanup_removes_disposable_installation_and_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            installation = output / "installation with spaces"
            database = output / "database"
            installation.mkdir()
            database.mkdir()
            log = output / "server.log"
            log.write_text("diagnostics", encoding="utf-8")
            results = []
            clean_disposable(output, installation, database, results)
            self.assertEqual(results[-1]["outcome"], "passed")
            self.assertFalse(installation.exists())
            self.assertFalse(database.exists())
            self.assertEqual(log.read_text(encoding="utf-8"), "diagnostics")

    def test_cleanup_retains_files_if_a_server_may_be_running(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            installation = output / "installation with spaces"
            database = output / "database"
            installation.mkdir()
            database.mkdir()
            (database / "postmaster.pid").write_text("123", encoding="ascii")
            results = []
            clean_disposable(output, installation, database, results)
            self.assertEqual(results[-1]["outcome"], "not_run")
            self.assertTrue(installation.exists())
            self.assertTrue(database.exists())


if __name__ == "__main__":
    unittest.main()
