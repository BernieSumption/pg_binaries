import importlib.util
from pathlib import Path
import json
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hypopg_macos_arm64_changed_profiles",
    ROOT / "tools" / "hypopg_macos_arm64_changed_profiles.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ChangedHypoPGMacOSArm64ProfilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.before = Path(self.temp.name) / "before"
        self.current = Path(self.temp.name) / "current"
        for root in (self.before, self.current):
            (root / "support").mkdir(parents=True)
            (root / "scripts").mkdir()
            for version in ("17.11", "18.6"):
                (root / "scripts" / f"probe-{version}.sql").write_text("SELECT 1;\n")
        profiles = {
            f"hypopg-publication-macos-arm64-{version}": {
                "scope": "publication", "platforms": ["macos-arm64"],
                "case_ids": ["archive-suite"],
                "sources": [f"scripts/probe-{version}.sql"]}
            for version in ("17.11", "18.6")
        }
        profiles["hypopg-publication-macos-x86_64-18.6"] = {
            "scope": "publication", "platforms": ["macos-x86_64"],
            "case_ids": ["archive-suite"], "sources": ["scripts/probe-18.6.sql"]}
        for root in (self.before, self.current):
            (root / "support" / "verification-profiles.json").write_text(
                json.dumps({"schema_version": 1, "profiles": profiles}))

    def tearDown(self):
        self.temp.cleanup()

    def test_unchanged_profiles_select_no_targets(self):
        self.assertEqual(module.changed_targets(self.before, self.current), [])

    def test_change_selects_only_affected_arm64_release(self):
        (self.current / "scripts" / "probe-18.6.sql").write_text("SELECT 2;\n")
        self.assertEqual(module.changed_targets(self.before, self.current), ["18.6"])

    def test_missing_base_profile_is_selected_fail_open(self):
        path = self.before / "support" / "verification-profiles.json"
        registry = json.loads(path.read_text())
        registry["profiles"].pop("hypopg-publication-macos-arm64-17.11")
        path.write_text(json.dumps(registry))
        self.assertEqual(module.changed_targets(self.before, self.current), ["17.11"])


if __name__ == "__main__":
    unittest.main()
