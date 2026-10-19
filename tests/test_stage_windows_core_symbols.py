import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage_windows_core_symbols as stage_symbols


CORE = "postgresql-18.6-windows-x86_64.tar.gz"
VECTOR = "pgvector-0.8.7-postgresql-18.6-windows-x86_64.tar.gz"


class StageWindowsCoreSymbolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.symbols = self.root / "artifact" / "debug-symbols"
        self.pdb = self.symbols / "pdbs" / "core.pdb"
        self.pdb.parent.mkdir(parents=True)
        self.pdb.write_bytes(b"core fixture bytes")
        self.entry = {"archive": CORE, "archive_sha256": "a" * 64,
                      "module_path": "postgresql/bin/postgres.exe", "module_sha256": "b" * 64,
                      "rsds_guid": "c" * 32, "rsds_age": 1,
                      "pdb_path": "pdbs/core.pdb", "pdb_sha256": "d" * 64}
        self._index([self.entry])

    def tearDown(self):
        self.temp.cleanup()

    def _index(self, entries, schema=1):
        self.symbols.mkdir(parents=True, exist_ok=True)
        (self.symbols / "index.json").write_text(
            json.dumps({"schema_version": schema, "files": entries}), encoding="utf-8")

    def test_copies_core_pdb_and_preserves_entry(self):
        paired = dict(self.entry, archive=VECTOR, module_path="pgvector/lib/vector.dll")
        self._index([self.entry, paired])
        destination = self.root / "staged"
        result = stage_symbols.stage(self.root / "artifact", destination, CORE)
        self.assertEqual(result, {"schema_version": 1, "files": [self.entry]})
        self.assertEqual((destination / "pdbs/core.pdb").read_bytes(), b"core fixture bytes")
        self.assertEqual(json.loads((destination / "index.json").read_text()), result)

    def test_rejects_unsupported_or_empty_index(self):
        self._index([self.entry], schema=2)
        with self.assertRaises(RuntimeError):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)
        self._index([])
        with self.assertRaises(RuntimeError):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)

    def test_rejects_unexpected_archive(self):
        self._index([dict(self.entry, archive="other.tar.gz")])
        with self.assertRaisesRegex(RuntimeError, "Unexpected archive"):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)

    def test_rejects_unsafe_and_duplicate_pdb_paths(self):
        for bad_path in ("../outside.pdb", "/tmp/outside.pdb", "pdbs\\core.pdb", "pdbs/not-pdb.txt"):
            with self.subTest(path=bad_path):
                self._index([dict(self.entry, pdb_path=bad_path)])
                with self.assertRaises(RuntimeError):
                    stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)
        self._index([self.entry, dict(self.entry, module_path="postgresql/bin/another.exe")])
        with self.assertRaisesRegex(RuntimeError, "Duplicate indexed PDB"):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)

    def test_rejects_missing_or_symlink_pdb(self):
        self.pdb.unlink()
        with self.assertRaisesRegex(RuntimeError, "missing"):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)
        outside = self.root / "elsewhere.pdb"
        outside.write_bytes(b"fixture")
        self.pdb.symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)


if __name__ == "__main__":
    unittest.main()
