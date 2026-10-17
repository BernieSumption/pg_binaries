import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_change_gate
import coverage


PROFILE_ID = "example-publication-x86_64"


def write_profile(root, profile_id=PROFILE_ID, case_ids=None, valid=True):
    root = Path(root)
    support = root / "support"
    support.mkdir(parents=True, exist_ok=True)
    (root / "profile-source.txt").write_text("profile source\n", encoding="utf-8")
    profile = {
        "scope": "publication",
        "case_ids": case_ids or ["archive-suite"],
        "platforms": ["macos-x86_64"],
        "sources": ["profile-source.txt"],
    }
    registry = {"schema_version": 1, "profiles": {profile_id: profile}}
    if not valid:
        registry["schema_version"] = 99
    (support / "verification-profiles.json").write_text(
        json.dumps(registry), encoding="utf-8")


class ProfileChangeGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.before = self.root / "before"
        self.current = self.root / "current"
        write_profile(self.before)
        write_profile(self.current)

    def tearDown(self):
        self.temporary.cleanup()

    def test_unchanged_profile_skips_platform_work(self):
        self.assertFalse(profile_change_gate.should_run(
            self.before, self.current, PROFILE_ID))

    def test_changed_profile_revision_runs_platform_work(self):
        write_profile(self.current, case_ids=["archive-suite", "diagnostics"])
        self.assertTrue(profile_change_gate.should_run(
            self.before, self.current, PROFILE_ID))

    def test_unrelated_registry_profile_change_skips_platform_work(self):
        registry_path = self.current / "support/verification-profiles.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["profiles"]["other-platform-publication"] = {
            "scope": "publication",
            "case_ids": ["other-case"],
            "platforms": ["windows-x86_64"],
            "sources": ["profile-source.txt"],
        }
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        self.assertFalse(profile_change_gate.should_run(
            self.before, self.current, PROFILE_ID))

    def test_missing_base_fails_open(self):
        self.assertTrue(profile_change_gate.should_run(
            self.root / "missing", self.current, PROFILE_ID))

    def test_invalid_base_fails_open(self):
        write_profile(self.before, valid=False)
        self.assertTrue(profile_change_gate.should_run(
            self.before, self.current, PROFILE_ID))

    def test_missing_base_profile_fails_open(self):
        write_profile(self.before, profile_id="other-publication")
        self.assertTrue(profile_change_gate.should_run(
            self.before, self.current, PROFILE_ID))

    def test_invalid_current_profile_is_an_error(self):
        write_profile(self.current, valid=False)
        with self.assertRaises(coverage.CoverageError):
            profile_change_gate.should_run(self.before, self.current, PROFILE_ID)


if __name__ == "__main__":
    unittest.main()
