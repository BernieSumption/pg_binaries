import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage_macos_core_symbols as stage_symbols


CORE = "postgresql-18.6-macos-arm64.tar.gz"
OTHER = "postgresql-18.6-macos-x86_64.tar.gz"


class StageMacOSCoreSymbolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.symbols = self.root / "artifact" / "debug-symbols"
        self.dsym = self.symbols / "dSYMs/postgresql/bin/postgres.dSYM"
        dwarf = self.dsym / "Contents/Resources/DWARF/postgres"
        dwarf.parent.mkdir(parents=True)
        dwarf.write_bytes(b"fixture dwarf")
        self.entry = {
            "archive": CORE, "archive_sha256": "a" * 64,
            "module_path": "postgresql/bin/postgres", "module_sha256": "b" * 64,
            "uuid": "1234", "architecture": "arm64",
            "dsym_path": "dSYMs/postgresql/bin/postgres.dSYM",
            "dsym_sha256": "c" * 64,
        }
        self._index([self.entry])

    def tearDown(self):
        self.temp.cleanup()

    def _index(self, entries, schema=1):
        self.symbols.mkdir(parents=True, exist_ok=True)
        (self.symbols / "index.json").write_text(
            json.dumps({"schema_version": schema, "files": entries}), encoding="utf-8")

    def test_stages_only_core_entries_and_unique_dsym_trees(self):
        duplicate_reference = dict(self.entry, module_path="postgresql/lib/libpq.5.dylib",
                                   uuid="5678")
        other = dict(self.entry, archive=OTHER, dsym_path="dSYMs/other.dSYM")
        self._index([self.entry, duplicate_reference, other])
        destination = self.root / "staged"
        result = stage_symbols.stage(self.root / "artifact", destination, CORE)
        self.assertEqual(result, {"schema_version": 1, "files": [self.entry, duplicate_reference]})
        self.assertEqual((destination / self.entry["dsym_path"] / "Contents/Resources/DWARF/postgres").read_bytes(),
                         b"fixture dwarf")
        self.assertFalse((destination / "dSYMs/other.dSYM").exists())
        self.assertEqual(json.loads((destination / "index.json").read_text()), result)

    def test_rejects_invalid_archive_and_index(self):
        with self.assertRaisesRegex(RuntimeError, "Invalid core archive"):
            stage_symbols.stage(self.root / "artifact", self.root / "out", "postgresql-18-macos-any.tar.gz")
        self._index([self.entry], schema=2)
        with self.assertRaises(RuntimeError):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)

    def test_rejects_unsafe_missing_and_symlink_paths(self):
        for bad in ("../outside.dSYM", "/tmp/outside.dSYM", "dSYMs\\bad.dSYM", "dSYMs/not.dSYM",
                    "dSYMs//postgresql/bin/postgres.dSYM",
                    "dSYMs/./postgresql/bin/postgres.dSYM", "other/postgres.dSYM"):
            with self.subTest(path=bad):
                self._index([dict(self.entry, dsym_path=bad)])
                with self.assertRaises(RuntimeError):
                    stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)
        self.dsym.rename(self.dsym.with_name("saved.dSYM"))
        self._index([self.entry])
        with self.assertRaisesRegex(RuntimeError, "missing"):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)
        self.dsym.symlink_to(self.dsym.with_name("saved.dSYM"), target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)

    def test_rejects_symlink_inside_tree_and_inconsistent_repeated_reference(self):
        outside = self.root / "outside"
        outside.write_bytes(b"outside")
        link = self.dsym / "Contents/Resources/DWARF/link"
        link.symlink_to(outside)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)
        link.unlink()
        self._index([self.entry, dict(self.entry, module_path="postgresql/bin/another",
                                      dsym_sha256="d" * 64)])
        with self.assertRaisesRegex(RuntimeError, "Conflicting checksums"):
            stage_symbols.stage(self.root / "artifact", self.root / "out", CORE)


if __name__ == "__main__":
    unittest.main()
