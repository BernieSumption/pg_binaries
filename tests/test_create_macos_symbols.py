import hashlib
import importlib.util
import tempfile
import tarfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "tools/create_macos_symbols.py"
SPEC = importlib.util.spec_from_file_location("create_macos_symbols", MODULE_PATH)
symbols = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(symbols)


class CreateMacosSymbolsTests(unittest.TestCase):
    def test_static_library_is_not_a_runtime_module(self):
        self.assertFalse(symbols.module_member("postgresql/lib/libecpg.a", set()))
        self.assertTrue(symbols.module_member("postgresql/lib/libpq.5.dylib", set()))
        self.assertTrue(symbols.module_member("pgaudit/lib/pgaudit.dylib", set()))
        self.assertTrue(symbols.module_member("hypopg/lib/hypopg.dylib", set()))
        self.assertTrue(symbols.module_member("pgvector/lib/vector.so", set()))
        self.assertFalse(symbols.module_member("pgaudit/share/unexpected.dylib", set()))
        self.assertFalse(symbols.module_member("hypopg/lib/libfoo.a", set()))
        self.assertFalse(symbols.module_member("hypopg/lib/dependency.dylib", {"dependency.dylib"}))

    def make_archive(self, directory, members):
        archive = directory / "pilot.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for name, data in members.items():
                path = directory / name.replace("/", "_")
                path.write_bytes(data)
                bundle.add(path, arcname=name)
        return archive

    def make_dsym(self, root):
        dwarf = root / "postgresql/bin/postgres.dSYM/Contents/Resources/DWARF/postgres"
        dwarf.parent.mkdir(parents=True)
        dwarf.write_bytes(b"debug data")
        return dwarf

    def test_indexes_finalized_uuid_and_copies_matching_dsym(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.make_archive(root, {
                "postgresql/bin/postgres": b"final postgres bytes",
                "postgresql/share/postgresql.conf.sample": b"not a binary",
                "pgvector/lib/vector.so": b"final vector bytes",
            })
            staged = root / "staged"
            dwarf = self.make_dsym(staged)
            output = root / "symbols"

            def fake_uuids(path):
                if path.name == "postgres":
                    return [("aa11", "arm64")]
                payload = path.read_bytes()
                return [("aa11", "arm64")] if payload in {
                    b"final postgres bytes", b"final vector bytes"
                } else []

            with patch.object(symbols, "uuids", side_effect=fake_uuids), \
                    patch.object(symbols, "has_dwarf", return_value=True):
                index = symbols.extract([archive], staged, output)

            self.assertEqual([item["module_path"] for item in index["files"]], [
                "postgresql/bin/postgres", "pgvector/lib/vector.so"
            ])
            first = index["files"][0]
            self.assertEqual(first["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(first["module_sha256"], hashlib.sha256(b"final postgres bytes").hexdigest())
            self.assertEqual(first["uuid"], "aa11")
            self.assertEqual(first["dsym_path"], "dSYMs/postgresql/bin/postgres.dSYM")
            copied = output / first["dsym_path"] / "Contents/Resources/DWARF/postgres"
            self.assertTrue(copied.is_file())
            self.assertEqual(first["dsym_sha256"], symbols.tree_sha256(output / first["dsym_path"]))
            output.mkdir(parents=True, exist_ok=True)
            (output / "index.json").write_text(__import__("json").dumps(index))
            with patch.object(symbols, "uuids", side_effect=fake_uuids), \
                    patch.object(symbols, "has_dwarf", return_value=True):
                symbols.verify([archive], output)

    def test_verify_rejects_changed_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.make_archive(root, {"postgresql/bin/postgres": b"final bytes"})
            staged = root / "staged"
            dwarf = self.make_dsym(staged)
            output = root / "symbols"
            with patch.object(symbols, "uuids", side_effect=lambda path: (
                [("aa11", "arm64")] if path.name == "postgres" or path.read_bytes() == b"final bytes" else []
            )), patch.object(symbols, "has_dwarf", return_value=True):
                index = symbols.extract([archive], staged, output)
                (output / "index.json").write_text(__import__("json").dumps(index))
                archive.write_bytes(b"changed archive")
                with self.assertRaisesRegex(RuntimeError, "Archive SHA-256 mismatch"):
                    symbols.verify([archive], output)

    def test_verify_rejects_missing_module_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.make_archive(root, {
                "postgresql/bin/postgres": b"postgres bytes",
                "pgvector/lib/vector.dylib": b"vector bytes",
            })
            staged = root / "staged"
            self.make_dsym(staged)
            output = root / "symbols"
            with patch.object(symbols, "uuids", return_value=[("aa11", "arm64")]), \
                    patch.object(symbols, "has_dwarf", return_value=True):
                index = symbols.extract([archive], staged, output)
                index["files"].pop()
                (output / "index.json").write_text(__import__("json").dumps(index))
                with self.assertRaisesRegex(RuntimeError, "coverage mismatch"):
                    symbols.verify([archive], output)

    def test_rejects_unsafe_tar_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "unsafe.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                info = tarfile.TarInfo("../escape")
                info.size = 1
                import io
                bundle.addfile(info, io.BytesIO(b"x"))
            with tarfile.open(archive, "r:gz") as bundle:
                with self.assertRaisesRegex(RuntimeError, "Unsafe tar member"):
                    symbols.validate_members(bundle)

    def test_fails_when_final_binary_uuid_has_no_staged_dsym(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.make_archive(root, {"postgresql/bin/postgres": b"final bytes"})
            staged = root / "staged"
            dwarf = self.make_dsym(staged)
            with patch.object(symbols, "uuids", side_effect=lambda path: (
                [("bb22", "arm64")] if path == dwarf else [("cc33", "arm64")]
            )):
                with self.assertRaisesRegex(RuntimeError, "No staged dSYM"):
                    symbols.extract([archive], staged, root / "symbols")


if __name__ == "__main__":
    unittest.main()
