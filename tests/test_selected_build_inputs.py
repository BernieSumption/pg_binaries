import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_input_identity
import selected_build_inputs


class SelectedBuildInputsTests(unittest.TestCase):
    PACKAGES_SHA256 = "c" * 64
    CORE_SHA256 = "b" * 64
    BASE_SHA256 = "0a9887931b0e38af2e3487ed39e29436b0535c4f3f52e57745baaf79d1898956"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copy(ROOT / "support.json", self.root / "support.json")
        for name in selected_build_inputs.RECIPE_FILES:
            source = ROOT / name
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, destination)

    def tearDown(self):
        self.temp.cleanup()

    def identity(self, major=18, packages_sha256=None, core_sha256=None):
        return selected_build_inputs.selected_identity(
            packages_sha256 or self.PACKAGES_SHA256, core_sha256 or self.CORE_SHA256,
            major, self.root)

    def support(self):
        path = self.root / "support.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        return path, value

    def test_unrelated_support_metadata_does_not_change_identity(self):
        first = self.identity()
        path, value = self.support()
        value["unrelated_review_note"] = "ignored by build inputs"
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(first, self.identity())

    def test_semantic_builder_identity_ignores_image_config_and_tracks_packages_and_base(self):
        first = self.identity()
        self.assertEqual(first["dependencies"]["builder_packages"]["sha256"],
                         self.PACKAGES_SHA256)
        self.assertEqual(first["dependencies"]["postgresql"]["sha256"], self.CORE_SHA256)
        self.assertEqual(first["dependencies"]["builder_base"], {
            "image": "ubuntu:22.04", "sha256": self.BASE_SHA256, "platform": "linux/amd64"})
        self.assertEqual(first, self.identity())
        self.assertNotEqual(first, self.identity(packages_sha256="d" * 64))
        self.assertNotEqual(first, self.identity(core_sha256="e" * 64))

        dockerfile = self.root / "scripts/pgvector/linux-build.Dockerfile"
        dockerfile.write_text(dockerfile.read_text(encoding="utf-8").replace(
            self.BASE_SHA256, "e" * 64), encoding="utf-8")
        changed_base = self.identity()
        self.assertNotEqual(first["sha256"], changed_base["sha256"])
        self.assertEqual(changed_base["dependencies"]["builder_base"]["sha256"], "e" * 64)

    def test_selected_postgresql_17_identity_binds_the_major_and_core_bytes(self):
        identity = self.identity(major=17)
        self.assertEqual(identity["target"]["postgresql_major"], 17)
        self.assertEqual(identity["dependencies"]["postgresql"], {
            "major": 17, "sha256": self.CORE_SHA256})
        self.assertEqual(identity["target"]["platform"], "linux-x86_64")

    def test_source_pin_recipe_major_and_platform_change_identity(self):
        first = self.identity()
        path, value = self.support()
        source = value["extensions"]["pgvector"]["versions"]["0.8.7"]["source_archives"]["tar.gz"]
        source["sha256"] = "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertNotEqual(first, self.identity())

        path, value = self.support()
        source = value["extensions"]["pgvector"]["versions"]["0.8.7"]["source_archives"]["tar.gz"]
        source["sha256"] = "cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85"
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(first, self.identity())
        recipe = self.root / "scripts/pgvector/linux-build.sh"
        recipe.write_text(recipe.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
        self.assertNotEqual(first, self.identity())

        changed_target = dict(first["target"], platform="macos-x86_64")
        changed = build_input_identity.create_identity(
            repo_root=self.root,
            component="pgvector",
            target=changed_target,
            upstream_sources={"pgvector": source},
            dependencies={"postgresql": {"major": 18}},
            build_configuration={"builder_image": "ubuntu:22.04", "architecture": "x86_64",
                                 "optflags": ""},
            recipe_files=selected_build_inputs.RECIPE_FILES,
        )
        self.assertNotEqual(first["sha256"], changed["sha256"])
        self.assertFalse(build_input_identity.assess_reuse(first, changed)["reusable"])

        changed_major = build_input_identity.create_identity(
            repo_root=self.root,
            component="pgvector",
            target=dict(first["target"], postgresql_major=19),
            upstream_sources={"pgvector": source},
            dependencies={"postgresql": {"major": 19, "sha256": self.CORE_SHA256},
                          "builder_packages": {"sha256": self.PACKAGES_SHA256},
                          "builder_base": {"image": "ubuntu:22.04", "sha256": self.BASE_SHA256,
                                           "platform": "linux/amd64"}},
            build_configuration={"builder_image": "ubuntu:22.04", "architecture": "x86_64",
                                 "optflags": ""},
            recipe_files=selected_build_inputs.RECIPE_FILES,
        )
        self.assertNotEqual(first["sha256"], changed_major["sha256"])

    def test_rejects_unsupported_target_major(self):
        with self.assertRaisesRegex(ValueError, "supports PostgreSQL majors 17 and 18"):
            self.identity(major=14)
        with self.assertRaisesRegex(ValueError, "builder packages SHA-256"):
            selected_build_inputs.selected_identity("ubuntu:22.04", self.CORE_SHA256, root=self.root)
        with self.assertRaisesRegex(ValueError, "builder packages SHA-256"):
            selected_build_inputs.selected_identity("sha256:" + self.PACKAGES_SHA256,
                                                    self.CORE_SHA256, root=self.root)
        with self.assertRaisesRegex(ValueError, "PostgreSQL core SHA-256"):
            selected_build_inputs.selected_identity(self.PACKAGES_SHA256, "sha256:" + self.CORE_SHA256,
                                                    root=self.root)


if __name__ == "__main__":
    unittest.main()
