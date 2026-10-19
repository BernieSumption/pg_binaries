import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools/check_linux_symbols.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("check_linux_symbols", MODULE_PATH)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class CheckLinuxSymbolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.symbols = self.root / "debug-symbols"
        self.symbols.mkdir()
        self.archive = self.root / "postgresql.tar.gz"
        self.archive.write_bytes(b"final archive")
        self.debug_file = self.symbols / "postgresql" / "postgresql/libexec/postgres.debug"
        self.debug_file.parent.mkdir(parents=True)
        self.debug_file.write_bytes(b"debug symbols")
        self.index_path = self.symbols / "index.json"
        self.write_index()

    def write_index(self, **changes):
        entry = {
            "archive": self.archive.name,
            "archive_sha256": hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            "debug_file_path": "postgresql/postgresql/libexec/postgres.debug",
            "debug_file_sha256": hashlib.sha256(self.debug_file.read_bytes()).hexdigest(),
        }
        entry.update(changes)
        self.index_path.write_text(json.dumps({"schema_version": 1, "files": [entry]}))

    def test_accepts_present_symbol_bound_to_exact_archive(self):
        self.assertEqual(checker.verify(self.index_path, [self.archive])["schema_version"], 1)

    def test_accepts_symbols_for_each_of_two_final_archives(self):
        extension = self.root / "pgvector.tar.gz"
        extension.write_bytes(b"final extension archive")
        extension_debug = self.symbols / "pgvector" / "pgvector/lib/vector.so.debug"
        extension_debug.parent.mkdir(parents=True)
        extension_debug.write_bytes(b"extension debug symbols")
        index = json.loads(self.index_path.read_text())
        index["files"].append({
            "archive": extension.name,
            "archive_sha256": hashlib.sha256(extension.read_bytes()).hexdigest(),
            "debug_file_path": "pgvector/pgvector/lib/vector.so.debug",
            "debug_file_sha256": hashlib.sha256(extension_debug.read_bytes()).hexdigest(),
        })
        self.index_path.write_text(json.dumps(index))
        self.assertEqual(len(checker.verify(self.index_path, [self.archive, extension])["files"]), 2)

    def test_rejects_archive_checksum_for_different_archive_bytes(self):
        self.archive.write_bytes(b"changed archive")
        with self.assertRaisesRegex(RuntimeError, "Archive SHA-256 mismatch"):
            checker.verify(self.index_path, [self.archive])

    def test_rejects_missing_debug_file(self):
        self.debug_file.unlink()
        with self.assertRaisesRegex(RuntimeError, "debug file is missing"):
            checker.verify(self.index_path, [self.archive])

    def test_rejects_changed_debug_file(self):
        self.debug_file.write_bytes(b"different debug symbols")
        with self.assertRaisesRegex(RuntimeError, "Debug-file SHA-256 mismatch"):
            checker.verify(self.index_path, [self.archive])

    def test_rejects_unsafe_debug_file_path(self):
        self.write_index(debug_file_path="../outside.debug")
        with self.assertRaisesRegex(RuntimeError, "Unsafe indexed debug-file path"):
            checker.verify(self.index_path, [self.archive])

    def test_rejects_unindexed_archive(self):
        second = self.root / "pgvector.tar.gz"
        second.write_bytes(b"another archive")
        with self.assertRaisesRegex(RuntimeError, "omits a supplied archive"):
            checker.verify(self.index_path, [self.archive, second])


if __name__ == "__main__":
    unittest.main()
