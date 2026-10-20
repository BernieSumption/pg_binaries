import unittest
from pathlib import Path
import json
import tempfile

from tools.coverage import verification_profile

from tools.pgaudit_macos_targets import target


class PgauditMacosTargetTests(unittest.TestCase):
    def test_selected_targets_have_publication_profiles(self):
        root = Path(__file__).resolve().parents[1]
        for version in ("15.19", "16.15", "17.11", "18.6"):
            with self.subTest(version=version):
                profile = verification_profile(root, target(version, "arm64")["profile_id"])
                self.assertEqual(profile["scope"], "publication")

    def test_pg15_target_uses_supplied_source_and_core_pins(self):
        selected = target("15.19", "arm64")
        self.assertEqual(selected["pgaudit_version"], "1.7.1")
        self.assertEqual(selected["core_sha256"], "")
        self.assertEqual(selected["core_build_id"], "")
        self.assertEqual(selected["core_source_revision"], "")
        self.assertEqual(selected["source_sha256"],
                         "1e52448238908a09e0e78b3375dcefbfca51509fdbb3a4d92eb710e380ed3567")

    def test_pg16_target_uses_supplied_source_and_core_pins(self):
        selected = target("16.15", "arm64")
        self.assertEqual(selected["pgaudit_version"], "16.1")
        self.assertEqual(selected["core_sha256"], "")
        self.assertEqual(selected["core_build_id"], "")
        self.assertEqual(selected["core_source_revision"], "")
        self.assertEqual(selected["source_sha256"],
                         "b0648fcebe5a67340c406126e6dddc703fd03821a9ace80390e128a0d1c91c73")

    def test_pg17_target_has_no_static_core_pin(self):
        selected = target("17.11", "arm64")
        self.assertEqual(selected["pgaudit_version"], "17.1")
        self.assertEqual(selected["core_sha256"], "")
        self.assertEqual(selected["profile_id"], "pgaudit-publication-macos-arm64-17.11")

    def test_targets_cover_both_selected_architectures_without_static_core_hashes(self):
        for version in ("15.19", "16.15", "17.11", "18.6"):
            for architecture in ("arm64", "x86_64"):
                with self.subTest(version=version, architecture=architecture):
                    selected = target(version, architecture)
                    self.assertEqual(selected["platform"], f"macos-{architecture}")
                    self.assertEqual(selected["profile_id"],
                                     f"pgaudit-publication-macos-{architecture}-{version}")
                    self.assertFalse(selected["resolved"])

    def test_resolved_core_target_is_required_for_publication(self):
        with self.assertRaisesRegex(ValueError, "resolved pgAudit macOS target config"):
            target("18.6", "x86_64", require_resolved=True)

    def test_resolved_target_binds_selected_architecture_source_and_core_identity(self):
        from tools import pgaudit_macos_targets
        with tempfile.TemporaryDirectory() as temporary:
            value = pgaudit_macos_targets._selected("16.15", "x86_64")
            value["core_archive"].update({"run_id": "123", "sha256": "a" * 64,
                                          "build_id": "github-123-2", "source_revision": "b" * 40})
            path = Path(temporary) / "target.json"
            path.write_text(json.dumps(value))
            selected = target("16.15", "x86_64", path, require_resolved=True)
            self.assertEqual(selected["core_sha256"], "a" * 64)
            self.assertEqual(selected["core_build_id"], "github-123-2")
            self.assertTrue(selected["resolved"])
            value["source"]["sha256"] = "0" * 64
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "does not match the selected"):
                target("16.15", "x86_64", path, require_resolved=True)

    def test_unregistered_target_is_rejected(self):
        with self.assertRaises(ValueError):
            target("14.17")


if __name__ == "__main__":
    unittest.main()
