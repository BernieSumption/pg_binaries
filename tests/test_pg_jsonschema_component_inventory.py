"""Tests for pg_jsonschema component inventories across Linux and macOS."""

import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_pg_jsonschema_component_inventory as checker


class ComponentInventoryTests(unittest.TestCase):
    def _archive(self, directory, module="pg_jsonschema.dylib", extra_notice=False, platform="macos"):
        notices = ["cargo/seahash-4.1.0/seahash-4.1.0-license-declaration.txt"]
        cargo = {"packages": [{
            "name": "pg_jsonschema", "version": "0.3.4", "license": None,
            "dependency_roles": ["root", "shipped"],
            "packaged_license_notice_files": [{"path": "cargo/pg_jsonschema-0.3.4/LICENSE"}],
        }, {
            "name": "seahash", "version": "4.1.0", "license": "MIT",
            "dependency_roles": ["shipped"],
            "packaged_license_notice_files": [{"path": notices[0]}],
        }]}
        if extra_notice:
            notices.append("cargo/extra-1/LICENSE")
        component = {"schema_version": 1, "components": [{
            "component": "pg_jsonschema", "version": "0.3.4",
            "payload_paths": [f"lib/{module}", "share/extension"],
            "license_file": "pg_jsonschema/LICENSE",
            "additional_license_files": sorted(notices + ["cargo/pg_jsonschema-0.3.4/LICENSE"]),
            "redistribution_review": {"status": "resolved", "basis": "Reviewed fixture terms.",
                                      "source_obligation": "none"},
        }]}
        entries = {
            "metadata.json": json.dumps({"platform": platform}).encode(),
            f"pg_jsonschema/lib/{module}": b"module",
            "pg_jsonschema/share/extension/pg_jsonschema.control": b"control",
            "pg_jsonschema/LICENSES/pg_jsonschema-inventory.json": json.dumps(component).encode(),
            "pg_jsonschema/LICENSES/cargo/cargo-license-inventory.json": json.dumps(cargo).encode(),
            "pg_jsonschema/LICENSES/pg_jsonschema/LICENSE": b"project licence",
            "pg_jsonschema/LICENSES/cargo/pg_jsonschema-0.3.4/LICENSE": b"root notice",
            "pg_jsonschema/LICENSES/cargo/seahash-4.1.0/seahash-4.1.0-license-declaration.txt": b"MIT declaration",
        }
        if extra_notice:
            entries["pg_jsonschema/LICENSES/cargo/extra-1/LICENSE"] = b"unlisted notice"
        path = Path(directory) / "package.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, content in entries.items():
                member = tarfile.TarInfo(name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        return path

    def test_accepts_macos_dylib_and_shipped_seahash_declaration(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(checker.validate(self._archive(directory)))

    def test_accepts_linux_so(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(checker.validate(self._archive(directory, module="pg_jsonschema.so", platform="linux")))

    def test_accepts_macos_pg15_so(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(checker.validate(self._archive(directory, module="pg_jsonschema.so")))

    def test_rejects_dylib_claimed_as_linux(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "payload_paths"):
                checker.validate(self._archive(directory, platform="linux"))

    def test_rejects_uncovered_notice_and_unknown_module_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "do not cover"):
                checker.validate(self._archive(directory, extra_notice=True))
            with self.assertRaisesRegex(ValueError, "payload_paths"):
                checker.validate(self._archive(directory, module="pg_jsonschema.dll"))


if __name__ == "__main__":
    unittest.main()
