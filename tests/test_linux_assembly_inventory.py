import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "linux_assembly_inventory", ROOT / "tools" / "linux_assembly_inventory.py")
assembly = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assembly)
SELECTOR_SPEC = importlib.util.spec_from_file_location(
    "select_extension_archive", ROOT / "tools" / "select_extension_archive.py")
selector = importlib.util.module_from_spec(SELECTOR_SPEC)
SELECTOR_SPEC.loader.exec_module(selector)


class LinuxAssemblyInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core = self.root / "postgresql-18.6-linux-x86_64.tar.gz"
        self.vector = self.root / "pgvector-0.8.7-postgresql-18.6-linux-x86_64.tar.gz"
        self.core.write_bytes(b"checked core")
        self.vector.write_bytes(b"checked extension")
        self.output = self.root / "assembly-inventory.json"

    def write(self, **overrides):
        values = dict(core_archive=self.core, extension_archive=self.vector,
                      postgresql_version="18.6", extension_version="0.8.7",
                      platform="linux-x86_64", output=self.output)
        values.update(overrides)
        return assembly.write_assembly_inventory(**values)

    def test_inventory_binds_exact_archive_bytes_and_one_selected_target(self):
        inventory = self.write()
        self.assertEqual(inventory["candidate_status"], "assembly-only")
        core_download = inventory["postgresql"]["18.6"]["downloads"]["linux-x86_64"]
        extension_download = inventory["extensions"]["vector"]["0.8.7"]["downloads"]["linux-x86_64"][0]
        self.assertEqual(core_download["sha256"], hashlib.sha256(self.core.read_bytes()).hexdigest())
        self.assertEqual(extension_download["sha256"], hashlib.sha256(self.vector.read_bytes()).hexdigest())
        self.assertEqual(extension_download["postgresql_support"], {"from": "18.6", "to": "18.6"})
        self.assertEqual(json.loads(self.output.read_text()), inventory)
        support = {"extensions": {"pgvector": {
            "sql_names": ["vector"], "versions": {"0.8.7": {}}}}}
        selected = selector.select_archive(inventory, support, "18.6", "linux-x86_64",
                                            "pgvector", "0.8.7", "vector")
        self.assertEqual(selected["sha256"], extension_download["sha256"])

    def test_rejects_wrong_target_filename_or_missing_archive(self):
        with self.assertRaisesRegex(assembly.AssemblyInventoryError, "filenames"):
            self.write(postgresql_version="17.11")
        self.vector.unlink()
        with self.assertRaisesRegex(assembly.AssemblyInventoryError, "missing"):
            self.write()
        self.assertFalse(self.output.exists())

    def test_cli_writes_inventory(self):
        result = subprocess.run([
            sys.executable, str(ROOT / "tools" / "linux_assembly_inventory.py"),
            "--core-archive", str(self.core), "--extension-archive", str(self.vector),
            "--postgresql-version", "18.6", "--extension-version", "0.8.7",
            "--platform", "linux-x86_64", "--output", str(self.output),
        ], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.output.read_text())["candidate_status"], "assembly-only")

    def test_linux_verifier_uses_inventory_staging_after_sidecar_checks(self):
        verifier = (ROOT / "scripts" / "linux" / "verify-in-container.sh").read_text()
        self.assertLess(verifier.index('sha256sum -c "$pg.sha256"'), verifier.index("linux-assembly-inventory"))
        self.assertLess(verifier.index('sha256sum -c "$vector.sha256"'), verifier.index("linux-assembly-inventory"))
        self.assertIn("--inventory /tmp/assembly-inventory.json", verifier)
        self.assertNotIn("--merge-payload", verifier)
        dockerfile = (ROOT / "scripts" / "linux" / "verify.Dockerfile").read_text()
        self.assertIn("tools/linux_assembly_inventory.py", dockerfile)
        self.assertIn("tools/select_extension_archive.py", dockerfile)
        self.assertIn("tools/coverage.py", dockerfile)


if __name__ == "__main__":
    unittest.main()
