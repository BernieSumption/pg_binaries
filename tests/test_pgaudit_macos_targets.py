import unittest

from tools.pgaudit_macos_targets import target


class PgauditMacosTargetTests(unittest.TestCase):
    def test_pg17_target_matches_checked_arm64_core_pin(self):
        selected = target("17.11")
        self.assertEqual(selected["pgaudit_version"], "17.1")
        self.assertEqual(selected["core_sha256"],
                         "d9ac809946cd87bbb585135d0ff329d33d5563047b9caaa312aea9116a8d9eaa")
        self.assertEqual(selected["core_build_id"], "github-39093804725-1")
        self.assertEqual(selected["core_source_revision"],
                         "42082a506adfca1628c509f2c7b17037b9a12123")

    def test_unregistered_target_is_rejected(self):
        with self.assertRaises(ValueError):
            target("16.15")


if __name__ == "__main__":
    unittest.main()
