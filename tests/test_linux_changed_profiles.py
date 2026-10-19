import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "linux_changed_profiles", ROOT / "tools" / "linux_changed_profiles.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class LinuxChangedProfilesTests(unittest.TestCase):
    def setUp(self):
        support = module.coverage.load_json(ROOT / "support.json")
        releases = module.coverage.load_json(ROOT / "support" / "postgresql-releases.json")
        plan = module.extension_archive_plan.plan(support, releases)
        self.expected = []
        for target in plan["candidate_archives"]:
            if target["project"] in {"HypoPG", "pg_jsonschema", "pgtap", "pg_ivm"} and target["platform"].startswith("linux-"):
                self.expected.append({
                    "project": target["project"],
                    "extension_version": target["selected_version"],
                    "postgresql_version": target["postgresql_version"],
                    "platform": target["platform"],
                })
        self.expected.sort(key=lambda item: (item["project"], item["postgresql_version"], item["platform"]))
        self.profile_ids = [module._profile_id({"HypoPG": "hypopg", "pg_jsonschema": "pg-jsonschema",
                                               "pgtap": "pgtap", "pg_ivm": "pgivm"}[item["project"]],
                                               item["platform"].split("-")[1],
                                               item["postgresql_version"])
                            for item in self.expected]

    def resolve_profiles(self, base, changed_id=None, unavailable_base=False, missing_id=None):
        def resolve(root, profile_id):
            if root == base and (unavailable_base or profile_id == missing_id):
                raise ValueError("base checkout is incomplete")
            architecture = "x86_64" if "x86_64" in profile_id else "arm64"
            revision = "old" if root == base and profile_id == changed_id else "current"
            return {"scope": "publication", "platforms": [f"linux-{architecture}"],
                    "profile_revision": revision}
        return resolve

    def test_initial_or_missing_base_selects_all_support_derived_targets(self):
        self.assertEqual(len(self.expected), len(self.profile_ids))
        self.assertEqual({target["project"] for target in self.expected},
                         {"HypoPG", "pg_jsonschema", "pgtap", "pg_ivm"})
        self.assertEqual({target["platform"] for target in self.expected},
                         {"linux-x86_64", "linux-arm64"})
        self.assertEqual(module.changed_targets(ROOT / "no-such-base", ROOT), self.expected)

    def test_same_profile_revisions_select_no_targets(self):
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(module.coverage, "verification_profile") as resolve:
            resolve.side_effect = self.resolve_profiles(base)
            self.assertEqual(module.changed_targets(base, ROOT), [])

    def test_one_changed_revision_selects_only_its_target(self):
        base = Path(tempfile.mkdtemp())
        target_profile = self.profile_ids[0]
        with mock.patch.object(module.coverage, "verification_profile") as resolve:
            resolve.side_effect = self.resolve_profiles(base, changed_id=target_profile)
            self.assertEqual(module.changed_targets(base, ROOT), [self.expected[0]])

    def test_base_profile_failure_fails_open_to_all_targets(self):
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(module.coverage, "verification_profile") as resolve:
            resolve.side_effect = self.resolve_profiles(base, unavailable_base=True)
            self.assertEqual(module.changed_targets(base, ROOT), self.expected)

    def test_new_profile_selects_only_its_target(self):
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(module.coverage, "verification_profile") as resolve:
            resolve.side_effect = self.resolve_profiles(base, missing_id=self.profile_ids[0])
            self.assertEqual(module.changed_targets(base, ROOT), [self.expected[0]])

    def test_manual_request_selects_one_declared_target(self):
        target = next(item for item in self.expected
                      if item["project"] == "pg_ivm"
                      and item["postgresql_version"] == "17.11"
                      and item["platform"] == "linux-arm64")
        self.assertEqual(module.changed_targets(None, ROOT, project="pg_ivm",
                         postgresql_version="17.11", architecture="arm64"), [target])
        with self.assertRaisesRegex(ValueError, "not declared"):
            module.changed_targets(None, ROOT, project="pg_ivm",
                                   postgresql_version="19.1", architecture="arm64")

    def test_matrix_limit_is_enforced(self):
        with mock.patch.object(module, "MAX_TARGETS", 1):
            with self.assertRaisesRegex(ValueError, "matrix exceeds"):
                module.changed_targets(None, ROOT)

    def test_two_versions_cannot_share_one_verification_profile(self):
        support = module.coverage.load_json(ROOT / "support.json")
        releases = module.coverage.load_json(ROOT / "support/postgresql-releases.json")
        plan = module.extension_archive_plan.plan(support, releases)
        duplicate = dict(next(target for target in plan["candidate_archives"]
                              if target["project"] == "pg_jsonschema"
                              and target["platform"].startswith("linux-")))
        duplicate["selected_version"] = "99.0.0"
        plan["candidate_archives"].append(duplicate)
        with mock.patch.object(module.extension_archive_plan, "plan", return_value=plan):
            with self.assertRaisesRegex(ValueError, "distinct profiles"):
                module.changed_targets(None, ROOT)


if __name__ == "__main__":
    unittest.main()
