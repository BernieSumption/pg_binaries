import json
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hypopg_build_inputs", ROOT / "scripts/hypopg/build_inputs.py")
build_inputs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_inputs)


class HypoPGSelectedBuildInputsTests(unittest.TestCase):
    CORE_SHA256 = "b" * 64
    PACKAGES_SHA256 = "c" * 64

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copy(ROOT / "support.json", self.root / "support.json")
        release_snapshot = self.root / "support/postgresql-releases.json"
        release_snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "support/postgresql-releases.json", release_snapshot)
        for name in build_inputs.RECIPE_FILES:
            source = ROOT / name
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, destination)

    def tearDown(self):
        self.temp.cleanup()

    def identity(self, core=None, packages=None, version="18.6", architecture="x86_64"):
        return build_inputs.selected_identity(core or self.CORE_SHA256,
                                              packages or self.PACKAGES_SHA256,
                                              version, architecture, self.root)

    def add_postgresql_release(self, version):
        path = self.root / "support/postgresql-releases.json"
        releases = json.loads(path.read_text(encoding="utf-8"))
        major = version.split(".", 1)[0]
        source = json.loads(json.dumps(next(
            release for release in releases["releases"] if release["version"] == "18.6")))
        source["version"] = version
        for archive in source["source_archives"].values():
            archive["url"] = archive["url"].replace("18.6", version)
        releases["releases"].append(source)
        path.write_text(json.dumps(releases), encoding="utf-8")

    def test_identity_binds_core_packages_target_and_build_recipes(self):
        first = self.identity()
        self.assertEqual(first, self.identity())
        self.assertEqual(first["dependencies"]["postgresql"], {
            "version": "18.6", "sha256": self.CORE_SHA256})
        self.assertEqual(first["dependencies"]["builder_packages"]["sha256"],
                         self.PACKAGES_SHA256)
        self.assertEqual(first["upstream_sources"]["hypopg"], build_inputs.SOURCE)
        self.assertNotEqual(first["sha256"], self.identity(core="d" * 64)["sha256"])
        self.assertNotEqual(first["sha256"], self.identity(packages="e" * 64)["sha256"])
        self.assertNotEqual(first["sha256"], self.identity(version="17.11")["sha256"])
        self.assertNotEqual(first["sha256"], self.identity(architecture="arm64")["sha256"])

        recipe = self.root / "scripts/hypopg/build-in-container.sh"
        recipe.write_text(recipe.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
        self.assertNotEqual(first["sha256"], self.identity()["sha256"])

    def test_probe_change_does_not_rebuild_unchanged_archive(self):
        before = self.identity()
        probe = self.root / "scripts/hypopg/probe.sql"
        probe.write_text("-- changed probe\n", encoding="utf-8")
        self.assertEqual(before, self.identity())

    def test_builder_base_pin_is_validated_and_bound_into_identity(self):
        first = self.identity()
        self.assertEqual(first["dependencies"]["builder_base"], {
            "image": "ubuntu:22.04",
            "sha256": "0a9887931b0e38af2e3487ed39e29436b0535c4f3f52e57745baaf79d1898956",
            "platform": "linux/amd64",
        })
        dockerfile = self.root / "scripts/hypopg/Dockerfile"
        dockerfile.write_text(dockerfile.read_text(encoding="utf-8").replace(
            "0a9887931b0e38af2e3487ed39e29436b0535c4f3f52e57745baaf79d1898956",
            "f" * 64), encoding="utf-8")
        self.assertNotEqual(first["sha256"], self.identity()["sha256"])
        dockerfile.write_text("FROM ubuntu:22.04\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pinned Ubuntu"):
            self.identity()

    def test_new_exact_release_in_repository_snapshot_needs_no_recipe_change(self):
        self.add_postgresql_release("18.7")
        identity = self.identity(version="18.7")
        self.assertEqual(identity["target"]["postgresql_version"], "18.7")
        self.assertEqual(identity["upstream_sources"]["postgresql"]["url"],
                         "https://ftp.postgresql.org/pub/source/v18.7/postgresql-18.7.tar.gz")
        with self.assertRaisesRegex(ValueError, "supported Linux matrix"):
            self.identity(version="18.8")

    def test_rejects_invalid_inputs_and_unselected_targets(self):
        with self.assertRaisesRegex(ValueError, "core SHA-256"):
            self.identity(core="sha256:" + self.CORE_SHA256)
        with self.assertRaisesRegex(ValueError, "supported Linux matrix"):
            self.identity(version="14.12")
        with self.assertRaisesRegex(ValueError, "architecture"):
            self.identity(architecture="riscv64")
        path = self.root / "support.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["platform_architectures"]["linux"].remove("arm64")
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not selected"):
            self.identity(architecture="arm64")


if __name__ == "__main__":
    unittest.main()
