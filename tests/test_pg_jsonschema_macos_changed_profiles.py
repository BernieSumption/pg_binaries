import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pg_jsonschema_macos_changed_profiles", ROOT / "tools" / "pg_jsonschema_macos_changed_profiles.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ChangedPgJsonschemaMacosProfilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.before = self.base / "before"
        self.current = self.base / "current"
        self.targets = self.base / "targets"
        self.targets.mkdir()
        self.source_by_profile = {}
        for filename in ("15.19-arm64.json", "15.19-x86_64.json"):
            shutil.copy(ROOT / "tools" / "pg_jsonschema_macos_targets" / filename, self.targets / filename)
            target = module.target_loader.load_target(self.targets / filename)
            self.source_by_profile[target.profile_id] = f"scripts/{target.architecture}.sql"
        self._write_root(self.before)
        self._write_root(self.current)

    def tearDown(self):
        self.temp.cleanup()

    def _write_root(self, root, wrong_platform=None):
        (root / "support").mkdir(parents=True, exist_ok=True)
        (root / "scripts").mkdir(exist_ok=True)
        profiles = {}
        for profile, source in self.source_by_profile.items():
            arch = "arm64" if "arm64" in profile else "x86_64"
            platform = wrong_platform if wrong_platform and arch == "arm64" else f"macos-{arch}"
            profiles[profile] = {"scope": "publication", "platforms": [platform],
                                 "case_ids": ["archive-suite", "static-analysis"], "sources": [source]}
            source_path = root / source
            source_path.write_text("SELECT 1;\n" if not source_path.exists() else source_path.read_text())
        (root / "support" / "verification-profiles.json").write_text(
            json.dumps({"schema_version": 1, "profiles": profiles}))

    def test_changed_profile_selects_only_its_target(self):
        (self.current / "scripts" / "arm64.sql").write_text("SELECT 2;\n")
        self.assertEqual(module.changed_targets(self.before, self.current, self.targets), [
            {"postgresql_version": "15.19", "extension_version": "0.3.4", "architecture": "arm64"}])

    def test_unchanged_profiles_select_none(self):
        self.assertEqual(module.changed_targets(self.before, self.current, self.targets), [])

    def test_missing_base_registry_selects_targets(self):
        shutil.rmtree(self.before / "support")
        self.assertEqual(len(module.changed_targets(self.before, self.current, self.targets)), 2)

    def test_architectures_remain_distinct_matrix_entries(self):
        selected = module.changed_targets(None, self.current, self.targets)
        self.assertEqual([item["architecture"] for item in selected], ["arm64", "x86_64"])
        self.assertEqual(len(selected), 2)

    def test_target_profile_declaration_mismatch_fails(self):
        self._write_root(self.current, wrong_platform="macos-x86_64")
        with self.assertRaisesRegex(ValueError, "does not match"):
            module.changed_targets(None, self.current, self.targets)

    def test_registered_profile_without_target_fails(self):
        registry_path = self.current / "support" / "verification-profiles.json"
        registry = json.loads(registry_path.read_text())
        registry["profiles"]["pg-jsonschema-publication-macos-arm64-19.0"] = {
            "scope": "publication", "platforms": ["macos-arm64"],
            "case_ids": ["archive-suite", "static-analysis"], "sources": ["scripts/arm64.sql"]}
        registry_path.write_text(json.dumps(registry))
        with self.assertRaisesRegex(ValueError, "targets and publication profiles differ"):
            module.changed_targets(None, self.current, self.targets)


if __name__ == "__main__":
    unittest.main()
