import hashlib
import importlib.util
import io
import json
import struct
import tarfile
import tempfile
import unittest
import uuid
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools/create_windows_symbols.py"
SPEC = importlib.util.spec_from_file_location("create_windows_symbols", MODULE_PATH)
symbols = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(symbols)


GUID = bytes.fromhex("00112233445566778899aabbccddeeff")
AGE = 7


def make_pe():
    """Build a small PE32 image with one RSDS CodeView record."""
    data = bytearray(0x600)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3c, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    coff = 0x84
    struct.pack_into("<HHIIIHH", data, coff, 0x14c, 1, 0, 0, 0, 224, 0)
    optional = coff + 20
    struct.pack_into("<H", data, optional, 0x10b)
    struct.pack_into("<I", data, optional + 92, 16)
    struct.pack_into("<II", data, optional + 96 + 6 * 8, 0x1000, 28)
    section = optional + 224
    data[section:section + 8] = b".rdata\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x200, 0x1000, 0x200, 0x400)
    struct.pack_into("<IIHHIIII", data, 0x400, 0, 0, 0, 0, 2, 32, 0x1000 + 28, 0x440)
    data[0x440:0x444] = b"RSDS"
    data[0x444:0x454] = GUID
    struct.pack_into("<I", data, 0x454, AGE)
    data[0x458:0x45f] = b"x.pdb\0\0"
    return bytes(data)


def make_pdb():
    """Build a two-stream MSF 7.0 file containing a minimal PDB Info stream."""
    block_size = 512
    info = struct.pack("<III", 20000404, 123, AGE) + GUID
    directory = struct.pack("<III", 2, 0, len(info)) + struct.pack("<I", 2)
    data = bytearray(block_size * 6)
    magic = b"Microsoft C/C++ MSF 7.00\r\n\x1aDS\0\0\0"
    data[:len(magic)] = magic
    struct.pack_into("<IIIIII", data, 32, block_size, 1, 6, len(directory), 0, 1)
    struct.pack_into("<I", data, block_size, 3)
    data[2 * block_size:2 * block_size + len(info)] = info
    data[3 * block_size:3 * block_size + len(directory)] = directory
    return bytes(data)


class CreateWindowsSymbolsTests(unittest.TestCase):
    def make_archive(self, directory, members):
        archive = directory / "pilot.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for name, data in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                bundle.addfile(info, io.BytesIO(data))
        return archive

    def test_parses_pe_rsds_and_pdb_msf_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pe, pdb = root / "sample.dll", root / "sample.pdb"
            pe.write_bytes(make_pe())
            pdb.write_bytes(make_pdb())
            expected_guid = uuid.UUID(bytes_le=GUID).hex
            self.assertEqual(symbols.pe_codeview(pe), (expected_guid, AGE))
            self.assertEqual(symbols.pdb_identity(pdb), (expected_guid, AGE))

    def test_rejects_pe_without_codeview_record(self):
        with tempfile.TemporaryDirectory() as temp:
            pe = Path(temp) / "without-debug.dll"
            data = bytearray(make_pe())
            struct.pack_into("<II", data, 0x98 + 96 + 6 * 8, 0, 0)
            pe.write_bytes(data)
            with self.assertRaisesRegex(RuntimeError, "no RSDS"):
                symbols.pe_codeview(pe)

    def test_indexes_archive_matches_staged_pdb_and_verifies_without_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.make_archive(root, {
                "postgresql/bin/postgres.exe": make_pe(),
                "postgresql/share/readme.txt": b"not a module",
                "pgvector/lib/vector.dll": make_pe(),
            })
            pg_build, vector_build = root / "pg-build", root / "vector-source"
            pg_build.mkdir()
            vector_build.mkdir()
            (pg_build / "postgres.pdb").write_bytes(make_pdb())
            # The same PDB can satisfy multiple modules. A second staged copy
            # would be an ambiguous duplicate and is intentionally not added.
            output = root / "symbols"
            index = symbols.extract([archive], [pg_build, vector_build], output)
            self.assertEqual([entry["module_path"] for entry in index["files"]], [
                "postgresql/bin/postgres.exe", "pgvector/lib/vector.dll"
            ])
            entry = index["files"][0]
            self.assertEqual(entry["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(entry["module_sha256"], hashlib.sha256(make_pe()).hexdigest())
            self.assertEqual(entry["pdb_sha256"], hashlib.sha256(make_pdb()).hexdigest())
            self.assertEqual((entry["rsds_guid"], entry["rsds_age"]), (uuid.UUID(bytes_le=GUID).hex, AGE))
            (output / "index.json").write_text(__import__("json").dumps(index))
            symbols.verify([archive], output)

    def test_rejects_missing_matching_pdb(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.make_archive(root, {"postgresql/bin/postgres.exe": make_pe()})
            staged = root / "staged"
            staged.mkdir()
            (staged / "wrong.pdb").write_bytes(make_pdb().replace(struct.pack("<I", AGE), struct.pack("<I", AGE + 1), 1))
            with self.assertRaisesRegex(RuntimeError, "No staged PDB"):
                symbols.extract([archive], [staged], root / "symbols")

    def test_verify_rejects_changed_archive_and_pdb(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.make_archive(root, {"postgresql/bin/postgres.exe": make_pe()})
            staged = root / "staged"
            staged.mkdir()
            (staged / "postgres.pdb").write_bytes(make_pdb())
            output = root / "symbols"
            index = symbols.extract([archive], [staged], output)
            (output / "index.json").write_text(__import__("json").dumps(index))
            pdb = output / index["files"][0]["pdb_path"]
            pdb.write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "PDB SHA-256 mismatch"):
                symbols.verify([archive], output)

    def test_ignores_non_pe_and_rejects_unsafe_tar_members(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            non_pe = root / "not-pe"
            non_pe.write_bytes(b"plain text")
            self.assertIsNone(symbols.pe_codeview(non_pe))
            archive = self.make_archive(root, {"../escape": b"x"})
            with tarfile.open(archive, "r:gz") as bundle:
                with self.assertRaisesRegex(RuntimeError, "Unsafe tar member"):
                    symbols.validate_members(bundle)

    def test_manifest_excludes_bundled_third_party_dlls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.make_archive(root, {
                "postgresql/manifest.json": json.dumps({"bundled_runtime_dlls": ["external.dll"]}).encode(),
                "postgresql/bin/postgres.exe": make_pe(),
                "postgresql/bin/external.dll": b"third-party image without matching PDB",
            })
            staged = root / "staged"
            staged.mkdir()
            (staged / "postgres.pdb").write_bytes(make_pdb())
            index = symbols.extract([archive], [staged], root / "symbols")
            self.assertEqual([entry["module_path"] for entry in index["files"]],
                             ["postgresql/bin/postgres.exe"])
            (root / "symbols/index.json").write_text(json.dumps(index))
            symbols.verify([archive], root / "symbols")


if __name__ == "__main__":
    unittest.main()
