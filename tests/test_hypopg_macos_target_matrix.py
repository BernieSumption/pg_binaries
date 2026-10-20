"""Check the selected HypoPG macOS publication targets."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
from hypopg_macos_target import base_target, load_target_config


class HypoPGMacOSTargetMatrixTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_selected_targets_have_matching_publication_profiles(self):
        expected = {
            ("15.19", "arm64"), ("15.19", "x86_64"),
            ("16.15", "arm64"), ("16.15", "x86_64"),
            ("17.11", "x86_64"),
        }
        targets = [base_target(version, arch, self.root) for version, arch in sorted(expected)]

        for target in targets:
            platform = f"macos-{target['architecture']}"
            profile = coverage.verification_profile(self.root, target["profile_id"])
            self.assertEqual(profile["scope"], "publication")
            self.assertEqual(profile["platforms"], [platform])
            self.assertEqual(profile["case_ids"], ["archive-suite", "static-analysis"])

            target["core_archive"]["sha256"] = "a" * 64
            with tempfile.TemporaryDirectory() as temporary:
                config = Path(temporary) / "target.json"
                config.write_text(json.dumps(target), encoding="utf-8")
                loaded = load_target_config(config, allow_base=True)
            self.assertEqual(loaded.profile_id, target["profile_id"])
            self.assertEqual(loaded.postgresql_version, target["postgresql_version"])
            self.assertEqual(loaded.architecture, target["architecture"])
            self.assertEqual(loaded.platform, platform)
            self.assertEqual(loaded.extension_basename,
                             f"hypopg-1.4.3-postgresql-{target['postgresql_version']}-{platform}.tar.gz")

    def test_target_loader_rejects_a_core_archive_from_another_release(self):
        target = base_target("17.11", "x86_64", self.root)
        target["core_archive"]["sha256"] = "a" * 64
        target["core_archive"]["basename"] = "postgresql-18.6-macos-x86_64.tar.gz"
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "target.json"
            config.write_text(json.dumps(target), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "inconsistent"):
                load_target_config(config, allow_base=True)


if __name__ == "__main__":
    unittest.main()
