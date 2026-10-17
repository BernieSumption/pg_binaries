import io
import json
import pathlib
import tarfile
import tempfile
import unittest

from tools.check_macos_license_inventory import InventoryError, check_archive


class MacOSLicenseInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.archive_path = pathlib.Path(self.temp.name) / "pilot.tar.gz"
        self.files = {
            "postgresql/LICENSES/inventory.json": json.dumps({
                "schema_version": 1,
                "components": [
                    {"component": "postgresql", "payload_paths": ["bin/postgres", "lib/libpq.dylib",
                                                                       "lib/postgresql/vector.so"],
                     "license_file": "PostgreSQL.txt",
                     "redistribution_review": {"status": "pending", "source_obligation": "unknown"}},
                    {"component": "lz4", "payload_paths": ["lib/liblz4.dylib"],
                     "license_file": "lz4.txt", "additional_license_files": ["lz4-notice.txt"],
                     "redistribution_review": {"status": "pending", "source_obligation": "unknown"}},
                ],
            }).encode(),
            "postgresql/LICENSES/PostgreSQL.txt": b"PostgreSQL licence",
            "postgresql/LICENSES/lz4.txt": b"LZ4 licence",
            "postgresql/LICENSES/lz4-notice.txt": b"Additional notice",
            "postgresql/bin/postgres": b"\xcf\xfa\xed\xfe" + b"binary",
            "postgresql/lib/libpq.dylib": b"library",
            "postgresql/lib/liblz4.dylib": b"library",
            "postgresql/lib/postgresql/vector.so": b"module",
        }
        self.links = {}
        self.write_archive()

    def tearDown(self):
        self.temp.cleanup()

    def write_archive(self):
        with tarfile.open(self.archive_path, "w:gz") as archive:
            for name, data in self.files.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            for name, target in self.links.items():
                member = tarfile.TarInfo(name)
                member.type = tarfile.SYMTYPE
                member.linkname = target
                archive.addfile(member)

    def test_accepts_complete_native_coverage_and_pending_review(self):
        self.assertEqual(check_archive(self.archive_path), (2, 4))

    def test_rejects_unmapped_native_module(self):
        inventory = json.loads(self.files["postgresql/LICENSES/inventory.json"])
        inventory["components"][0]["payload_paths"].remove("lib/libpq.dylib")
        self.files["postgresql/LICENSES/inventory.json"] = json.dumps(inventory).encode()
        self.write_archive()
        with self.assertRaisesRegex(InventoryError, "unmapped native payload: lib/libpq.dylib"):
            check_archive(self.archive_path)

    def test_rejects_missing_declared_license(self):
        del self.files["postgresql/LICENSES/lz4-notice.txt"]
        self.write_archive()
        with self.assertRaisesRegex(InventoryError, "missing or empty declared licence text"):
            check_archive(self.archive_path)

    def test_rejects_payload_path_traversal(self):
        inventory = json.loads(self.files["postgresql/LICENSES/inventory.json"])
        inventory["components"][0]["payload_paths"][0] = "../outside"
        self.files["postgresql/LICENSES/inventory.json"] = json.dumps(inventory).encode()
        self.write_archive()
        with self.assertRaisesRegex(InventoryError, "invalid payload path"):
            check_archive(self.archive_path)

    def test_accepts_safe_symlink_payload_to_regular_library(self):
        inventory = json.loads(self.files["postgresql/LICENSES/inventory.json"])
        inventory["components"][1]["payload_paths"].append("lib/liblz4-link.dylib")
        self.files["postgresql/LICENSES/inventory.json"] = json.dumps(inventory).encode()
        self.links["postgresql/lib/liblz4-link.dylib"] = "liblz4.dylib"
        self.write_archive()
        self.assertEqual(check_archive(self.archive_path), (2, 5))

    def test_rejects_escaping_dangling_and_cyclic_payload_symlinks(self):
        inventory = json.loads(self.files["postgresql/LICENSES/inventory.json"])
        inventory["components"][1]["payload_paths"].append("lib/liblz4-link.dylib")
        self.files["postgresql/LICENSES/inventory.json"] = json.dumps(inventory).encode()
        for target, message in (("../../outside.dylib", "escapes component root"),
                                ("missing.dylib", "dangling or non-regular"),
                                ("liblz4-cycle.dylib", "cyclic archive symlink")):
            self.links["postgresql/lib/liblz4-link.dylib"] = target
            if target == "liblz4-cycle.dylib":
                self.links["postgresql/lib/liblz4-cycle.dylib"] = "liblz4-link.dylib"
            else:
                self.links.pop("postgresql/lib/liblz4-cycle.dylib", None)
            self.write_archive()
            with self.subTest(target=target), self.assertRaisesRegex(InventoryError, message):
                check_archive(self.archive_path)


if __name__ == "__main__":
    unittest.main()
