import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "tools/inventory_cargo_licenses.py"
spec = importlib.util.spec_from_file_location("inventory_cargo_licenses", MODULE_PATH)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CargoLicenseInventoryTests(unittest.TestCase):
    def metadata(self, packages, edges):
        root = packages[0]["id"]
        return {
            "packages": packages,
            "resolve": {
                "root": root,
                "nodes": [{"id": package["id"], "deps": edges.get(package["id"], [])}
                          for package in packages],
            },
        }

    def test_records_sorted_packages_and_hashed_license_and_notice_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "LICENSE").write_text("root license\n")
            crate = root / "vendor/example-1.0"
            crate.mkdir(parents=True)
            (crate / "Cargo.toml").write_text("[package]\nname='example'\n")
            (crate / "LICENSE-MIT").write_text("MIT terms\n")
            (crate / "NOTICE").write_text("notice text\n")
            package = {
                "id": "example 1.0.0 (registry+https://example.invalid)",
                "name": "example", "version": "1.0.0", "source": "registry+https://example.invalid",
                "license": "MIT", "license_file": None, "manifest_path": str(crate / "Cargo.toml"),
            }
            metadata = self.metadata([package], {})

            result = checker.inventory(root, metadata)

            self.assertEqual(result["source_files"][0]["path"], "LICENSE")
            self.assertEqual([f["path"] for f in result["packages"][0]["license_notice_files"]], ["LICENSE-MIT", "NOTICE"])
            self.assertEqual(len(result["packages"][0]["license_notice_files"][0]["sha256"]), 64)
            self.assertEqual(result["packages"][0]["dependency_roles"], ["root", "shipped"])

    def test_classifies_linked_and_host_tooling_closures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packages = []
            for name, targets in [
                ("extension", [{"kind": ["lib"], "crate_types": ["lib"]}]),
                ("runtime", [{"kind": ["lib"], "crate_types": ["lib"]}]),
                ("macro", [{"kind": ["proc-macro"], "crate_types": ["proc-macro"]}]),
                ("macro-helper", [{"kind": ["lib"], "crate_types": ["lib"]}]),
                ("builder", [{"kind": ["lib"], "crate_types": ["lib"]}]),
                ("build-helper", [{"kind": ["lib"], "crate_types": ["lib"]}]),
                ("dev-only", [{"kind": ["lib"], "crate_types": ["lib"]}]),
            ]:
                crate = root / name
                crate.mkdir()
                manifest = crate / "Cargo.toml"
                manifest.touch()
                packages.append({"id": name, "name": name, "version": "1.0.0",
                                 "manifest_path": str(manifest), "targets": targets})

            def edge(pkg, kind=None):
                return {"pkg": pkg, "dep_kinds": [{"kind": kind, "target": None}]}

            edges = {
                "extension": [edge("runtime"), edge("macro"), edge("builder", "build"), edge("dev-only", "dev")],
                "runtime": [], "macro": [edge("macro-helper")], "macro-helper": [],
                "builder": [edge("build-helper")], "build-helper": [], "dev-only": [],
            }
            result = checker.inventory(root, self.metadata(packages, edges))
            roles = {package["name"]: package["dependency_roles"] for package in result["packages"]}

            self.assertEqual(roles["extension"], ["root", "shipped"])
            self.assertEqual(roles["runtime"], ["shipped"])
            self.assertEqual(roles["macro"], ["host_tooling", "proc_macro"])
            self.assertEqual(roles["macro-helper"], ["host_tooling", "normal_dependency"])
            self.assertEqual(roles["builder"], ["build_dependency", "host_tooling"])
            self.assertEqual(roles["build-helper"], ["host_tooling", "normal_dependency"])
            self.assertEqual(roles["dev-only"], ["dev_dependency", "host_tooling"])

    def test_package_reached_by_both_runtime_and_host_paths_keeps_both_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packages = []
            for name in ("extension", "shared"):
                crate = root / name
                crate.mkdir()
                manifest = crate / "Cargo.toml"
                manifest.touch()
                packages.append({"id": name, "name": name, "version": "1.0.0",
                                 "manifest_path": str(manifest), "targets": []})
            metadata = self.metadata(packages, {
                "extension": [
                    {"pkg": "shared", "dep_kinds": [{"kind": None, "target": None}]},
                    {"pkg": "shared", "dep_kinds": [{"kind": "build", "target": None}]},
                ],
            })

            result = checker.inventory(root, metadata)

            self.assertEqual(result["packages"][1]["dependency_roles"],
                             ["build_dependency", "host_tooling", "shipped"])

    def test_records_package_without_license_metadata_for_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crate = root / "crate"
            crate.mkdir()
            manifest = crate / "Cargo.toml"
            manifest.touch()
            package = {"id": "missing", "name": "missing", "version": "1", "manifest_path": str(manifest)}
            metadata = self.metadata([package], {})

            result = checker.inventory(root, metadata)
            self.assertTrue(result["packages"][0]["license_metadata_missing"])
            self.assertEqual(result["packages"][0]["license_notice_files"], [])

    def test_rejects_missing_declared_license_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crate = root / "crate"
            crate.mkdir()
            manifest = crate / "Cargo.toml"
            manifest.touch()
            metadata = {"packages": [{
                "id": "missing-file", "name": "missing-file", "version": "1", "license_file": "LICENSE.txt",
                "manifest_path": str(manifest),
            }], "resolve": {"root": "missing-file", "nodes": [{"id": "missing-file", "deps": []}]}}

            with self.assertRaisesRegex(ValueError, "invalid or missing license_file"):
                checker.inventory(root, metadata)


if __name__ == "__main__":
    unittest.main()
