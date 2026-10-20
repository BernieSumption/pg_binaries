import unittest
from pathlib import Path

from tools.coverage import verification_profile

from tools.pgaudit_macos_targets import target


class PgauditMacosTargetTests(unittest.TestCase):
    def test_selected_targets_have_publication_profiles(self):
        root = Path(__file__).resolve().parents[1]
        for version in ("15.19", "16.15", "17.11", "18.6"):
            with self.subTest(version=version):
                profile = verification_profile(root, target(version)["profile_id"])
                self.assertEqual(profile["scope"], "publication")

    def test_pg15_target_uses_supplied_source_and_core_pins(self):
        selected = target("15.19")
        self.assertEqual(selected["pgaudit_version"], "1.7.1")
        self.assertEqual(selected["core_sha256"],
                         "856956cd7615bc56222de954c83f156fe5bc73d75512d230c6b91d386229f432")
        self.assertEqual(selected["core_build_id"], "github-39093804765-1")
        self.assertEqual(selected["source_sha256"],
                         "1e52448238908a09e0e78b3375dcefbfca51509fdbb3a4d92eb710e380ed3567")

    def test_pg16_target_uses_supplied_source_and_core_pins(self):
        selected = target("16.15")
        self.assertEqual(selected["pgaudit_version"], "16.1")
        self.assertEqual(selected["core_sha256"],
                         "716083752061eebab60923ae2e8cb269bc2e4bdb7401d951465cd726a50e6cbf")
        self.assertEqual(selected["core_build_id"], "github-39093805055-1")
        self.assertEqual(selected["source_sha256"],
                         "b0648fcebe5a67340c406126e6dddc703fd03821a9ace80390e128a0d1c91c73")

    def test_pg17_target_matches_checked_arm64_core_pin(self):
        selected = target("17.11")
        self.assertEqual(selected["pgaudit_version"], "17.1")
        self.assertEqual(selected["core_sha256"],
                         "7c8522779eb2ab4e93c863bccc72865c59b60a21ef1cd507323e300413d5d568")
        self.assertEqual(selected["core_build_id"], "github-39420673533-1")
        self.assertEqual(selected["core_source_revision"],
                         "bf0284b528dc8188c7b01bacf2f13d21fce7ee88")

    def test_unregistered_target_is_rejected(self):
        with self.assertRaises(ValueError):
            target("14.17")


if __name__ == "__main__":
    unittest.main()
