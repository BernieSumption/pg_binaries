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
    BUILDER_ID = "sha256:" + "c" * 64

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

    def identity(self, major=18):
        return selected_build_inputs.selected_identity(self.BUILDER_ID, major, self.root)

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
            dependencies={"postgresql": {"major": 19},
                          "builder_image": {"id": self.BUILDER_ID}},
            build_configuration={"builder_image": "ubuntu:22.04", "architecture": "x86_64",
                                 "optflags": ""},
            recipe_files=selected_build_inputs.RECIPE_FILES,
        )
        self.assertNotEqual(first["sha256"], changed_major["sha256"])

    def test_rejects_unsupported_target_major(self):
        with self.assertRaisesRegex(ValueError, "supports PostgreSQL major 18 only"):
            self.identity(major=14)
        with self.assertRaisesRegex(ValueError, "builder image ID"):
            selected_build_inputs.selected_identity("ubuntu:22.04", root=self.root)


if __name__ == "__main__":
    unittest.main()
