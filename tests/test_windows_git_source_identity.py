import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location(
    "check_windows_git_source_identity", ROOT / "tools" / "check_windows_git_source_identity.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)
from postgresql_git_source import source_checkout


class WindowsGitSourceIdentityTests(unittest.TestCase):
    def test_pins_release_tag_commit_and_tree(self):
        self.assertEqual(source_checkout("16.15"), {
            "repository": "https://github.com/postgres/postgres.git",
            "ref": "refs/tags/REL_16_15",
            "commit": "7d3e000c5961a544302072058a1184e9a588837b",
            "tree": "e97d2bd54137833e68079ed70e1a4a6621453264",
        })
        with self.assertRaisesRegex(ValueError, "no pinned"):
            source_checkout("17.11")

    def test_validator_accepts_checkout_and_rejects_untruthful_tarball_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            core_path, vector_path = Path(temp) / "manifest.json", Path(temp) / "vector.json"
            core = {"source_checkout": source_checkout("16.15")}
            vector = {"source_archive": checker.source_archive("pgvector", "0.8.7", "tar.gz")}
            core_path.write_text(json.dumps(core), encoding="utf-8")
            vector_path.write_text(json.dumps(vector), encoding="utf-8")
            checker.check(ROOT, "16.15", core_path, vector_path)
            core["source_checkout"]["commit"] = "0" * 40
            core_path.write_text(json.dumps(core), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Git source identity"):
                checker.check(ROOT, "16.15", core_path, vector_path)
            core = {"source_checkout": source_checkout("16.15"),
                    "source_archive": checker.source_archive("postgresql", "16.15", "tar.gz")}
            core_path.write_text(json.dumps(core), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not claim"):
                checker.check(ROOT, "16.15", core_path, vector_path)
            with self.assertRaisesRegex(ValueError, "only configured"):
                checker.check(ROOT, "17.11", core_path, vector_path)


if __name__ == "__main__":
    unittest.main()
