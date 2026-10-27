from pathlib import Path
import tempfile
import unittest

from verification.macos.runtime import clean_disposable, verify


class RuntimeChecksTests(unittest.TestCase):
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
