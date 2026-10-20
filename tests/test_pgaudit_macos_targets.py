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
                         "bd866dec8967e6320f88eb8ffe3a2f57fad36920b3d05556dae026c53226cf85")
        self.assertEqual(selected["core_build_id"], "github-39424367764-1")
        self.assertEqual(selected["core_source_revision"],
                         "817362a98376ab8b0a5af6239ae5dbc92962fedf")
        self.assertEqual(selected["source_sha256"],
                         "1e52448238908a09e0e78b3375dcefbfca51509fdbb3a4d92eb710e380ed3567")

    def test_pg16_target_uses_supplied_source_and_core_pins(self):
        selected = target("16.15")
        self.assertEqual(selected["pgaudit_version"], "16.1")
        self.assertEqual(selected["core_sha256"],
                         "aae8b4e67a88cb3edc074070527dda23ea5bac09b7574403fdaa18eb1e31ab8c")
        self.assertEqual(selected["core_build_id"], "github-39424382435-1")
        self.assertEqual(selected["core_source_revision"],
                         "817362a98376ab8b0a5af6239ae5dbc92962fedf")
        self.assertEqual(selected["source_sha256"],
                         "b0648fcebe5a67340c406126e6dddc703fd03821a9ace80390e128a0d1c91c73")

    def test_pg17_target_matches_checked_arm64_core_pin(self):
        selected = target("17.11")
        self.assertEqual(selected["pgaudit_version"], "17.1")
        self.assertEqual(selected["core_sha256"],
                         "0db9ca0f4d0cf72fa32120aaf9a3f8e47c9dd2d97421ab2b53583af83be681b6")
        self.assertEqual(selected["core_build_id"], "github-39425313739-1")
        self.assertEqual(selected["core_source_revision"],
                         "408cb35e340df85bd8664771188b20e82ab6bc64")

    def test_unregistered_target_is_rejected(self):
        with self.assertRaises(ValueError):
            target("14.17")


if __name__ == "__main__":
    unittest.main()
