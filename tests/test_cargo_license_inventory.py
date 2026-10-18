import importlib.util
import json
import tempfile
import tarfile
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

    def packaging_fixture(self, root):
        packages = []
        for name, version in [("extension", "1"), ("builder", "1"),
                              ("seahash", "4.1.0")] + [(name, data[0]) for name, data in checker.SUPPLEMENTS.items()]:
            crate = root / name
            crate.mkdir()
            manifest = crate / "Cargo.toml"
            manifest.touch()
            if name in checker.SUPPLEMENTS:
                (crate / ".cargo_vcs_info.json").write_text(json.dumps(
                    {"git": {"sha1": checker.SUPPLEMENTS[name][1]}}))
            if name == "extension":
                (crate / "LICENSE").write_text("extension licence")
            packages.append({"id": name, "name": name, "version": version,
                             "manifest_path": str(manifest),
                             "source": "registry+https://github.com/rust-lang/crates.io-index"})
        edges = {"extension": [{"pkg": p["id"], "dep_kinds": [{"kind": "build" if p["id"] == "builder" else None}]}
                               for p in packages[1:]]}
        metadata = self.metadata(packages, edges)
        return metadata, checker.inventory(root / "extension", metadata)

    def test_packages_and_checks_actual_source_texts_and_five_supplements(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            metadata, result = self.packaging_fixture(root)
            payload = root / "stage/pg_jsonschema"
            supplements = MODULE_PATH.parents[1] / "support/evidence/pg-jsonschema-crate-licenses-2026-10-18"
            checker.package_notices(result, metadata, payload, supplements)
            shipped = [p for p in result["packages"] if "shipped" in p["dependency_roles"]]
            self.assertEqual(sum(bool(p["packaged_license_notice_files"]) for p in shipped), 6)
            self.assertEqual(result["packaging"]["missing_notice_packages"][0]["name"], "seahash")
            self.assertFalse((payload / "LICENSES/cargo/builder-1").exists())
            inventory_path = payload / "LICENSES/pg_jsonschema-cargo-license-inventory.json"
            inventory_path.write_text(json.dumps(result))
            archive_path = root / "extension.tar.gz"

            def archive():
                with tarfile.open(archive_path, "w:gz") as output:
                    output.add(payload, arcname="pg_jsonschema")
                return tarfile.open(archive_path, "r:gz")

            with archive() as output:
                checker.check_packaged_notices(output, "pg_jsonschema/LICENSES/pg_jsonschema-cargo-license-inventory.json")
            notice = payload / "LICENSES/cargo/pgrx-0.16.1/upstream-LICENSE"
            notice.write_text("altered notice")
            with archive() as output:
                with self.assertRaisesRegex(ValueError, "changed notice"):
                    checker.check_packaged_notices(output, "pg_jsonschema/LICENSES/pg_jsonschema-cargo-license-inventory.json")

    def test_rejects_unexpected_missing_text_and_changed_supplement_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            metadata, result = self.packaging_fixture(root)
            supplements = MODULE_PATH.parents[1] / "support/evidence/pg-jsonschema-crate-licenses-2026-10-18"
            (root / "pgrx/.cargo_vcs_info.json").write_text('{"git": {"sha1": "different"}}')
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                checker.package_notices(result, metadata, root / "payload", supplements)
            (root / "pgrx/.cargo_vcs_info.json").write_text(json.dumps(
                {"git": {"sha1": checker.SUPPLEMENTS["pgrx"][1]}}))
            (root / "extension/LICENSE").unlink()
            result = checker.inventory(root / "extension", metadata)
            with self.assertRaisesRegex(ValueError, "unexpected unresolved"):
                checker.package_notices(result, metadata, root / "payload", supplements)

    def test_records_sorted_packages_and_hashed_license_and_notice_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "LICENSE").write_text("root license\n")
            crate = root / "vendor/example-1.0"
            crate.mkdir(parents=True)
            (crate / "Cargo.toml").write_text("[package]\nname='example'\n")
            (crate / "LICENSE-MIT").write_text("MIT terms\n")
            (crate / "NOTICE").write_text("notice text\n")
            (crate / "LICENSES").mkdir()
            (crate / "LICENSES/MIT.txt").write_text("separate MIT terms\n")
            package = {
                "id": "example 1.0.0 (registry+https://example.invalid)",
                "name": "example", "version": "1.0.0", "source": "registry+https://example.invalid",
                "license": "MIT", "license_file": None, "manifest_path": str(crate / "Cargo.toml"),
            }
            metadata = self.metadata([package], {})

            result = checker.inventory(root, metadata)

            self.assertEqual(result["source_files"][0]["path"], "LICENSE")
            self.assertEqual([f["path"] for f in result["packages"][0]["license_notice_files"]],
                             ["LICENSE-MIT", "LICENSES/MIT.txt", "NOTICE"])
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

    def test_includes_explicit_license_file_with_unusual_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "terms.txt").write_text("applicable terms")
            package = {"id": "root", "name": "root", "version": "1",
                       "manifest_path": str(root / "Cargo.toml"), "license_file": "terms.txt"}
            result = checker.inventory(root, self.metadata([package], {}))
            self.assertEqual(result["packages"][0]["license_notice_files"][0]["path"], "terms.txt")

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
