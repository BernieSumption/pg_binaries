import importlib.util
from pathlib import Path
import json
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hypopg_windows_changed_profiles", ROOT / "tools" / "hypopg_windows_changed_profiles.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ChangedHypoPGWindowsProfilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.before = Path(self.temp.name) / "before"
        self.current = Path(self.temp.name) / "current"
        for root in (self.before, self.current):
            (root / "support").mkdir(parents=True)
            (root / "scripts").mkdir()
            for version in ("15.19", "16.15", "17.11", "18.6"):
                (root / "scripts" / f"probe-{version}.sql").write_text("SELECT 1;\n")
        profiles = {
            f"hypopg-publication-windows-x86_64-{version}": {
                "scope": "publication", "platforms": ["windows-x86_64"],
                "case_ids": ["archive-suite"],
                "sources": [f"scripts/probe-{version}.sql"]}
            for version in ("15.19", "16.15", "17.11", "18.6")
        }
        for root in (self.before, self.current):
            (root / "support" / "verification-profiles.json").write_text(
                json.dumps({"schema_version": 1, "profiles": profiles}))

    def tearDown(self):
        self.temp.cleanup()

    def test_unchanged_profiles_select_no_targets(self):
        self.assertEqual(module.changed_targets(self.before, self.current), [])

    def test_shared_source_change_selects_only_declared_affected_profiles(self):
        (self.current / "scripts" / "probe-17.11.sql").write_text("SELECT 2;\n")
        self.assertEqual(module.changed_targets(self.before, self.current), ["17.11"])

    def test_registry_may_declare_one_profile_without_selecting_others(self):
        path = self.current / "support" / "verification-profiles.json"
        registry = json.loads(path.read_text())
        registry["profiles"].pop("hypopg-publication-windows-x86_64-15.19")
        path.write_text(json.dumps(registry))
        self.assertEqual(module.changed_targets(self.before, self.current), [])


if __name__ == "__main__":
    unittest.main()
