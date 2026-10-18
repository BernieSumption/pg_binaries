import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hypopg_changed_profiles", ROOT / "tools" / "hypopg_changed_profiles.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ChangedHypoPGProfilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.before = Path(self.temp.name) / "before"
        self.current = Path(self.temp.name) / "current"
        self.profiles = {
            "hypopg-publication-windows-x86_64-15.19": "windows-15.sql",
            "hypopg-publication-windows-x86_64-20.1": "windows-20.sql",
            "hypopg-publication-macos-arm64-18.6": "macos-18.sql",
            "hypopg-publication-macos-x86_64-18.6": "other-platform.sql",
        }
        for root in (self.before, self.current):
            (root / "support").mkdir(parents=True)
            (root / "scripts").mkdir()
            registry = {}
            for profile_id, source in self.profiles.items():
                platform = "windows-x86_64" if "windows" in profile_id else (
                    "macos-arm64" if "macos-arm64" in profile_id else "macos-x86_64")
                registry[profile_id] = {
                    "scope": "publication", "platforms": [platform],
                    "case_ids": ["archive-suite"], "sources": [f"scripts/{source}"]}
                (root / "scripts" / source).write_text("SELECT 1;\n")
            (root / "support" / "verification-profiles.json").write_text(
                json.dumps({"schema_version": 1, "profiles": registry}))

    def tearDown(self):
        self.temp.cleanup()

    def test_unchanged_profiles_select_no_targets(self):
        self.assertEqual(module.changed_targets(
            self.before, self.current, "hypopg-publication-windows-x86_64-"), [])

    def test_prefix_selects_all_current_matching_profiles_without_version_list(self):
        (self.current / "scripts" / "windows-20.sql").write_text("SELECT 2;\n")
        self.assertEqual(module.changed_targets(
            self.before, self.current, "hypopg-publication-windows-x86_64-"), ["20.1"])

    def test_matching_platform_is_scoped_by_profile_prefix(self):
        (self.current / "scripts" / "macos-18.sql").write_text("SELECT 2;\n")
        self.assertEqual(module.changed_targets(
            self.before, self.current, "hypopg-publication-macos-arm64-"), ["18.6"])

    def test_missing_base_profile_is_selected_fail_open(self):
        path = self.before / "support" / "verification-profiles.json"
        registry = json.loads(path.read_text())
        registry["profiles"].pop("hypopg-publication-macos-arm64-18.6")
        path.write_text(json.dumps(registry))
        self.assertEqual(module.changed_targets(
            self.before, self.current, "hypopg-publication-macos-arm64-"), ["18.6"])

    def test_missing_or_zero_before_root_selects_every_current_target(self):
        self.assertEqual(module.changed_targets(
            None, self.current, "hypopg-publication-windows-x86_64-"), ["15.19", "20.1"])


if __name__ == "__main__":
    unittest.main()
