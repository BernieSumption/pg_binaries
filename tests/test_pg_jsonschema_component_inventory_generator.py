"""Tests for generating resolved pg_jsonschema component inventories."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import create_pg_jsonschema_component_inventory as generator


class ComponentInventoryGeneratorTests(unittest.TestCase):
    def _package(self, directory, dependency_license="MIT", dependency_notices=None):
        root = Path(directory)
        (root / "LICENSES/pg_jsonschema").mkdir(parents=True)
        (root / "LICENSES/cargo/cargo-license-inventory.json").parent.mkdir(parents=True)
        (root / "LICENSES/pg_jsonschema/LICENSE").write_text("Apache-2.0 project licence\n")
        root_notice = "cargo/pg_jsonschema-0.3.4/LICENSE"
        dep_notice = "cargo/example-1.2.3/NOTICE"
        notices = [{"path": "NOTICE"}] if dependency_notices is None else dependency_notices
        (root / "LICENSES" / root_notice).parent.mkdir(parents=True)
        (root / "LICENSES" / root_notice).write_text("root package notice\n")
        if notices:
            (root / "LICENSES" / dep_notice).parent.mkdir(parents=True)
            (root / "LICENSES" / dep_notice).write_text("dependency notice\n")
        cargo = {"schema_version": 1, "packages": [
            {"name": "pg_jsonschema", "version": "0.3.4", "license": None,
             "dependency_roles": ["root", "shipped"],
             "packaged_license_notice_files": [{"path": root_notice}]},
            {"name": "example", "version": "1.2.3", "license": dependency_license,
             "dependency_roles": ["shipped"], "packaged_license_notice_files": notices},
        ]}
        (root / "LICENSES/cargo/cargo-license-inventory.json").write_text(json.dumps(cargo))
        return root

    def test_generates_same_review_and_cargo_paths_for_each_platform(self):
        expected_notices = [
            "cargo/example-1.2.3/NOTICE", "cargo/pg_jsonschema-0.3.4/LICENSE",
        ]
        for platform, module in (("linux", "pg_jsonschema.so"),
                                 ("macos", "pg_jsonschema.dylib"),
                                 ("windows", "pg_jsonschema.dll")):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as directory:
                output = generator.generate(self._package(directory), "0.3.4", platform, module)
                inventory = json.loads(output.read_text())
                component = inventory["components"][0]
                self.assertEqual(component["payload_paths"], [f"lib/{module}", "share/extension"])
                self.assertEqual(component["additional_license_files"], expected_notices)
                self.assertEqual(component["redistribution_review"]["status"], "resolved")
                self.assertEqual(component["redistribution_review"]["source_obligation"], "none")
                self.assertIn("seahash MIT declaration", component["redistribution_review"]["basis"])

    def test_rejects_unknown_license_and_missing_notice(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "licence requires review"):
                generator.generate(self._package(directory, dependency_license="AGPL-3.0"),
                                   "0.3.4", "linux", "pg_jsonschema.so")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "lacks packaged notices"):
                generator.generate(self._package(directory, dependency_notices=[]),
                                   "0.3.4", "linux", "pg_jsonschema.so")

    def test_rejects_module_suffix_for_the_wrong_platform(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self._package(directory)
            with self.assertRaisesRegex(ValueError, "not supported for linux"):
                generator.generate(package, "0.3.4", "linux", "pg_jsonschema.dll")
            with self.assertRaisesRegex(ValueError, "not supported for windows"):
                generator.generate(package, "0.3.4", "windows", "pg_jsonschema.so")

    def test_rejects_unreviewed_extension_version(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "does not cover"):
                generator.generate(self._package(directory), "0.4.0", "linux", "pg_jsonschema.so")


if __name__ == "__main__":
    unittest.main()
