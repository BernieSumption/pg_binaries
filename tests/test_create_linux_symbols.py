import hashlib
import importlib.util
import tempfile
import tarfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "tools/create_linux_symbols.py"
SPEC = importlib.util.spec_from_file_location("create_linux_symbols", MODULE_PATH)
symbols = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(symbols)


class CreateLinuxSymbolsTests(unittest.TestCase):
    def make_archive(self, directory, members):
        archive = directory / "pilot.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for name, data in members.items():
                path = directory / name.replace("/", "_")
                path.write_bytes(data)
                bundle.add(path, arcname=name)
        return archive

    def test_indexes_finalized_module_and_separate_debug_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.make_archive(root, {
            "postgresql/libexec/postgres": b"\x7fELF postgres",
                "postgresql/lib/runtime/libc.so": b"\x7fELF runtime",
                "pgvector/lib/vector.so": b"\x7fELF vector",
            })
            output = root / "symbols"

            def fake_run(command, **kwargs):
                if command[0] == "objcopy":
                    Path(command[-1]).write_bytes(b"debug symbols")

            with patch.object(symbols, "build_id", side_effect=["ab12", "ab12", "cd34", "cd34"]), \
                    patch.object(symbols, "has_dwarf", return_value=True), \
                    patch.object(symbols.subprocess, "run", side_effect=fake_run):
                index = symbols.extract([archive], output)

            self.assertEqual([item["module_path"] for item in index["files"]], [
                "postgresql/libexec/postgres", "pgvector/lib/vector.so"
            ])
            first = index["files"][0]
            self.assertEqual(first["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(first["module_sha256"], hashlib.sha256(b"\x7fELF postgres").hexdigest())
            self.assertEqual(first["debug_file_sha256"], hashlib.sha256(b"debug symbols").hexdigest())
            self.assertEqual(first["gnu_build_id"], "ab12")

    def test_fails_when_archived_elf_has_no_build_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.make_archive(root, {"postgresql/libexec/postgres": b"\x7fELF postgres"})
            with patch.object(symbols, "build_id", side_effect=RuntimeError("ELF file has no GNU build ID")):
                with self.assertRaisesRegex(RuntimeError, "no GNU build ID"):
                    symbols.extract([archive], root / "symbols")


if __name__ == "__main__":
    unittest.main()
