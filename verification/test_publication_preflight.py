import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from verification.publication_preflight import PreflightError, check
from verification.inventory import RELEASE_BASE


class PublicationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.support_path = self.root / "support.json"
        self.support = {
            "targets": {"macos-arm64": {}},
            "packages": {"pgvector": {"extensions": {"vector": {}}}},
        }
        self.support_path.write_text(json.dumps(self.support))
        self.paths = {}
        archives = {}
        components = {}
        for name in ("postgresql", "pgvector"):
            path = self.root / f"{name}.tar.gz"
            with tarfile.open(path, "w:gz") as output:
                directory = tarfile.TarInfo("postgresql")
                directory.type = tarfile.DIRTYPE
                output.addfile(directory)
                payload = b"See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md"
                licence = tarfile.TarInfo("postgresql/LICENCE")
                licence.size = len(payload)
                output.addfile(licence, io.BytesIO(payload))
                control_name = "citext" if name == "postgresql" else "vector"
                control = tarfile.TarInfo(f"postgresql/share/postgresql/extension/{control_name}.control")
                control.size = 1
                output.addfile(control, io.BytesIO(b"x"))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            archives[name] = {"filename": path.name, "sha256": digest,
                              "origin_run": 7 if name == "postgresql" else 8}
            components[name] = {"archive": str(path), "sha256": digest,
                                "origin_run": archives[name]["origin_run"]}
        self.paths = {name: self.root / f"{name}.tar.gz" for name in archives}
        report = {"target": "macos-arm64", "archives": archives,
                  "combinations": [{"name": name, "outcome": "passed"}
                                   for name in ("postgresql-only", "pgvector", "all-packages")],
                  "postgresql_builtin_extensions": ["citext"]}
        selection = {"target": "macos-arm64", "components": components}
        self.report_path, self.selection_path = self.root / "report.json", self.root / "selection.json"
        self.report_path.write_text(json.dumps(report))
        self.selection_path.write_text(json.dumps(selection))
        self.inventory = {
            "extensions": {"vector": {"package": "pgvector"}, "citext": {"package": "postgresql"}},
            "packages": {name: {"downloads": {"macos-arm64": {
                "url": f"{RELEASE_BASE}/candidate/{record['filename']}",
                "sha256": record["sha256"]}}}
                         for name, record in archives.items()},
        }
        self.inventory_path = self.root / "inventory.json"
        self.save_inventory()

    def save_inventory(self):
        self.inventory_path.write_text(json.dumps(self.inventory))

    def test_passes_complete_local_preflight(self):
        count = check(self.inventory_path,
                      [("macos-arm64", self.selection_path, self.report_path)], self.support_path)
        self.assertEqual(count, 1)

    def test_rejects_wrong_inventory_sha(self):
        self.inventory["packages"]["pgvector"]["downloads"]["macos-arm64"]["sha256"] = "0" * 64
        self.save_inventory()
        with self.assertRaisesRegex(PreflightError, "does not match"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_wrong_extension_package_mapping(self):
        self.inventory["extensions"]["vector"]["package"] = "postgresql"
        self.save_inventory()
        with self.assertRaisesRegex(PreflightError, "do not match verification report"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)

    def test_rejects_download_url_for_other_bytes(self):
        self.inventory["packages"]["pgvector"]["downloads"]["macos-arm64"]["url"] = (
            f"{RELEASE_BASE}/candidate/other.tar.gz")
        self.save_inventory()
        with self.assertRaisesRegex(PreflightError, "download does not match"):
            check(self.inventory_path,
                  [("macos-arm64", self.selection_path, self.report_path)], self.support_path)


if __name__ == "__main__":
    unittest.main()
