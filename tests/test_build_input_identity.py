import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_input_identity as tool


class BuildInputIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "recipe.py").write_text("build()\n", encoding="utf-8")
        (self.root / "config.json").write_text("{}\n", encoding="utf-8")
        self.args = {
            "repo_root": self.root,
            "component": "demo",
            "target": "linux-x86_64",
            "upstream_sources": {"demo": {"revision": "abc", "sha256": "a" * 64}},
            "dependencies": {"lib": {"version": "1", "sha256": "b" * 64}},
            "build_configuration": {"flags": ["-O2"], "mode": "release"},
            "recipe_files": ["recipe.py", "config.json"],
        }

    def tearDown(self):
        self.temp.cleanup()

    def identity(self, **updates):
        return tool.create_identity(**(self.args | updates))

    def test_canonical_identity_ignores_mapping_and_recipe_order(self):
        first = self.identity(recipe_files=["recipe.py", "config.json"])
        self.assertEqual(first, self.identity(recipe_files=["config.json", "recipe.py"]))
        self.assertEqual(first, self.identity(
            upstream_sources={"demo": {"sha256": "a" * 64, "revision": "abc"}},
            build_configuration={"mode": "release", "flags": ["-O2"]},
        ))

    def test_assessment_requires_exact_identity_and_valid_digest(self):
        identity = self.identity()
        self.assertTrue(tool.assess_reuse(identity, identity)["reusable"])
        self.assertFalse(tool.assess_reuse(identity, None)["reusable"])
        changed = dict(identity, target="macos-arm64")
        result = tool.assess_reuse(identity, changed)
        self.assertFalse(result["reusable"])
        self.assertIn("digest", result["reason"])
        self.assertIn("unsupported schema", tool.assess_reuse(identity, {"schema_version": 9})["reason"])

    def test_rejects_missing_duplicate_escaping_and_bad_hash_inputs(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.identity(recipe_files=["absent.py"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.identity(recipe_files=["recipe.py", "./recipe.py"])
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.identity(recipe_files=["../outside.py"])
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.identity(upstream_sources={"demo": {"sha256": "ABC"}})


if __name__ == "__main__":
    unittest.main()
