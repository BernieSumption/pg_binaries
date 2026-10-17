import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "plan_work", Path(__file__).resolve().parents[1] / "tools" / "plan_work.py")
plan_work = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan_work)


class PlanWorkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.support = {
            "schema_version": 1,
            "version_selection_as_of": "2026-10-17",
            "postgresql": {"minimum_major": 15},
            "os_support": {name: {"minimum_version": "1"}
                           for name in ("macos", "windows", "linux")},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"], "linux": ["x86_64", "arm64"]},
            "extensions": {"Example": {"sql_names": ["example"], "versions": {
                "1.0": {"postgresql_minimum_major": 15}}}},
        }
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01", "supported_majors": [15]},
                    "releases": [{"version": "15.9", "release_date": "2025-09-25"}]}
        self.write("support.json", self.support)
        self.write("support/postgresql-releases.json", snapshot)
        self.write("inventory.json", {"postgresql": {}, "extensions": {}})
        self.root.joinpath("policies/extensions.md").parent.mkdir(parents=True, exist_ok=True)
        self.root.joinpath("policies/extensions.md").write_text(
            "## Example — include\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def write_pilot_records(self, record_specs, architecture="x86_64", stale=False):
        source = self.root / "tests/fixture.sh"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("suite", encoding="utf-8")
        profile_id = f"fixture-{architecture}"
        self.write("support/verification-profiles.json", {
            "schema_version": 1,
            "profiles": {profile_id: {
                "scope": "pilot-smoke", "platforms": ["linux-arm64", "linux-x86_64"],
                "case_ids": ["case-a", "case-b"], "sources": ["tests/fixture.sh"]}},
        })
        profile = plan_work.coverage.verification_profile(self.root, profile_id)
        records_dir = self.root / "support/verification"
        records_dir.mkdir(parents=True, exist_ok=True)
        for path in records_dir.glob("*.json"):
            path.unlink()
        for index, (version, endpoint, checksum, outcome, component, pg_version,
                    record_platform) in enumerate(record_specs):
            record_architecture = record_platform.split("-", 1)[1]
            record = {
                "schema_version": 2, "scope": "pilot-smoke", "profile_id": profile_id,
                "profile_revision": profile["profile_revision"], "outcome": outcome,
                "sha256": checksum, "component": component, "version": version,
                "platform": record_platform, "postgresql_version": pg_version,
                "test_revision": "a" * 40, "test_cases": profile["case_ids"],
                "environment": {"os": "linux", "architecture": record_architecture,
                                "os_version": "1" if endpoint == "minimum" else "2",
                                "clean_system": True, "endpoint": endpoint,
                                "image_id": "ubuntu@sha256:image",
                                "dependency_check_profile": "linux-runtime-v1",
                                "dependency_checks_passed": True},
            }
            (records_dir / f"record-{index}.json").write_text(json.dumps(record), encoding="utf-8")
        if stale:
            source.write_text("changed suite", encoding="utf-8")

    def test_missing_archives_are_builds_and_unverified_downloads_are_checks(self):
        checksum = "a" * 64
        platform = "linux-x86_64"
        inventory = {
            "postgresql": {"15.9": {"downloads": {platform: {
                "url": "https://example.test/postgres.tgz", "sha256": checksum}}}},
            "extensions": {"example": {"1.0": {"downloads": {platform: [{
                "postgresql_support": {"from": "15.0", "to": "15.9"},
                "url": "https://example.test/ext.tgz", "sha256": checksum}]}}}},
        }
        self.write("inventory.json", inventory)
        result = plan_work.plan(self.root)
        self.assertEqual(result["build_missing"]["core"], [
            ["15.9", "linux-arm64"], ["15.9", "macos-arm64"],
            ["15.9", "macos-x86_64"], ["15.9", "windows-x86_64"]])
        self.assertEqual(result["verify_downloaded"]["core"], [["15.9", platform]])
        self.assertEqual(result["build_missing"]["extensions"], [
            ["example", "1.0", "15.9", p] for p in
            ("linux-arm64", "macos-arm64", "macos-x86_64", "windows-x86_64")])
        self.assertEqual(result["verify_downloaded"]["extensions"], [
            ["example", "1.0", "15.9", platform]])

    def test_linux_pilot_accepts_new_stable_major_from_snapshot(self):
        snapshot = {"as_of": "2027-01-01", "source": "https://example.test/releases",
                    "support_status": {"as_of": "2027-01-01", "source": "https://example.test/support",
                                       "supported_majors": [19]},
                    "releases": [{"version": "19.0", "release_date": "2026-11-01"}]}
        self.write("support/postgresql-releases.json", snapshot)
        self.assertEqual(plan_work.select_linux_pilot(self.root, "19.0")["postgresql_version"], "19.0")

    def test_passed_matching_records_remove_downloaded_work(self):
        checksum = "b" * 64
        platform = "linux-x86_64"
        self.write("inventory.json", {"postgresql": {"15.9": {"downloads": {platform: {
            "url": "https://example.test/postgres.tgz", "sha256": checksum}}}},
            "extensions": {}})
        records_dir = self.root / "support/verification"
        records_dir.mkdir(parents=True)
        profile_sources = self.root / "tests" / "fixture.sh"
        profile_sources.parent.mkdir(parents=True, exist_ok=True)
        profile_sources.write_text("suite", encoding="utf-8")
        profile_registry = {"schema_version": 1, "profiles": {"fixture-linux": {
            "scope": "publication", "platforms": [platform], "case_ids": ["case-a", "case-b"],
            "sources": ["tests/fixture.sh"]}}}
        self.write("support/verification-profiles.json", profile_registry)
        profile = plan_work.coverage.verification_profile(self.root, "fixture-linux")
        for endpoint in ("minimum", "current"):
            record = {"schema_version": 2, "scope": profile["scope"], "profile_id": profile["profile_id"],
                      "profile_revision": profile["profile_revision"], "outcome": "passed", "sha256": checksum, "component": "postgresql",
                      "version": "15.9", "platform": platform, "postgresql_version": "15.9",
                      "test_revision": "a" * 40, "test_cases": profile["case_ids"],
                      "case_results": {case: "passed" for case in profile["case_ids"]},
                      "environment": {"os": "linux", "architecture": "x86_64",
                                      "os_version": "1" if endpoint == "minimum" else "2", "clean_system": True,
                                      "endpoint": endpoint, "image_id": "ubuntu@sha256:image",
                                      "dependency_check_profile": "linux-runtime-v1",
                                      "dependency_checks_passed": True}}
            (records_dir / f"{endpoint}.json").write_text(json.dumps(record), encoding="utf-8")
        result = plan_work.plan(self.root)
        self.assertNotIn(["15.9", platform], result["verify_downloaded"]["core"])

        profile_sources.write_text("changed suite", encoding="utf-8")
        stale = plan_work.plan(self.root)
        self.assertIn(["15.9", platform], stale["verify_downloaded"]["core"])
        self.assertEqual(stale["stale_verification_records"], 2)

    def test_output_is_stable(self):
        first = plan_work.plan(self.root)
        second = plan_work.plan(self.root)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_linux_pilot_selects_declared_missing_fifteen_through_eighteen_targets(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01", "supported_majors": [15, 16, 17, 18]},
                    "releases": [{"version": "15.19", "release_date": "2025-09-25"},
                                 {"version": "16.15", "release_date": "2025-09-25"},
                                 {"version": "17.11", "release_date": "2025-09-25"},
                                 {"version": "18.0", "release_date": "2025-09-25"}]}
        self.write("support/postgresql-releases.json", snapshot)
        self.assertEqual(plan_work.select_linux_pilot(self.root, "15.19"), {
            "postgresql_version": "15.19", "platform": "linux-x86_64",
            "work": "build_missing", "snapshot_as_of": "2026-01-01"})
        self.assertEqual(plan_work.select_linux_pilot(self.root, "16.15"), {
            "postgresql_version": "16.15", "platform": "linux-x86_64",
            "work": "build_missing", "snapshot_as_of": "2026-01-01"})
        self.assertEqual(plan_work.select_linux_pilot(self.root, "17.11"), {
            "postgresql_version": "17.11", "platform": "linux-x86_64",
            "work": "build_missing", "snapshot_as_of": "2026-01-01"})
        self.assertEqual(plan_work.select_linux_pilot(self.root, "18.0"), {
            "postgresql_version": "18.0", "platform": "linux-x86_64",
            "work": "build_missing", "snapshot_as_of": "2026-01-01"})
        self.assertEqual(plan_work.select_linux_pilot(self.root, "18.0", "arm64"), {
            "postgresql_version": "18.0", "platform": "linux-arm64",
            "work": "build_missing", "snapshot_as_of": "2026-01-01"})
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "architecture must be"):
            plan_work.select_linux_pilot(self.root, "18.0", "ppc64le")
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "at least 15"):
            plan_work.select_linux_pilot(self.root, "14.9")
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "not a missing declared"):
            plan_work.select_linux_pilot(self.root, "18.9")

    def test_linux_pilot_rejects_existing_public_download(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01", "supported_majors": [15]},
                    "releases": [{"version": "15.19", "release_date": "2025-09-25"}]}
        self.write("support/postgresql-releases.json", snapshot)
        self.write("inventory.json", {"postgresql": {"15.19": {"downloads": {
            "linux-x86_64": {"url": "https://example.test/pg.tgz", "sha256": "a" * 64}}}},
            "extensions": {}})
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "not a missing declared"):
            plan_work.select_linux_pilot(self.root, "15.19")

    def test_linux_arm64_pilot_rejects_existing_public_download(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01", "supported_majors": [15]},
                    "releases": [{"version": "15.19", "release_date": "2025-09-25"}]}
        self.write("support/postgresql-releases.json", snapshot)
        self.write("inventory.json", {"postgresql": {"15.19": {"downloads": {
            "linux-arm64": {"url": "https://example.test/pg-arm64.tgz", "sha256": "a" * 64}}}},
            "extensions": {}})
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "not a missing declared"):
            plan_work.select_linux_pilot(self.root, "15.19", "arm64")

    def test_next_linux_pilot_selects_highest_missing_declared_target(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01", "supported_majors": [15, 16, 18]},
                    "releases": [{"version": "15.9", "release_date": "2025-09-25"},
                                 {"version": "16.11", "release_date": "2025-09-25"},
                                 {"version": "18.2", "release_date": "2025-09-25"}]}
        self.write("support/postgresql-releases.json", snapshot)
        self.assertEqual(plan_work.select_next_linux_pilot(self.root), {
            "postgresql_version": "18.2", "platform": "linux-x86_64",
            "work": "build_missing", "snapshot_as_of": "2026-01-01"})
        self.assertEqual(plan_work.select_next_linux_pilot(self.root, "arm64"), {
            "postgresql_version": "18.2", "platform": "linux-arm64",
            "work": "build_missing", "snapshot_as_of": "2026-01-01"})

    def test_next_linux_pilot_skips_downloaded_target_and_rejects_empty_architecture(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01", "supported_majors": [15, 18]},
                    "releases": [{"version": "15.9", "release_date": "2025-09-25"},
                                 {"version": "18.2", "release_date": "2025-09-25"}]}
        self.write("support/postgresql-releases.json", snapshot)
        checksum = "a" * 64
        self.write("inventory.json", {"postgresql": {
            "18.2": {"downloads": {"linux-x86_64": {
                "url": "https://example.test/postgres.tgz", "sha256": checksum}}}},
            "extensions": {}})
        self.assertEqual(plan_work.select_next_linux_pilot(self.root)["postgresql_version"], "15.9")
        self.write("inventory.json", {"postgresql": {
            version: {"downloads": {"linux-x86_64": {
                "url": f"https://example.test/{version}.tgz", "sha256": checksum}}}
            for version in ("15.9", "18.2")}, "extensions": {}})
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "no missing declared core build"):
            plan_work.select_next_linux_pilot(self.root)
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "architecture must be"):
            plan_work.select_next_linux_pilot(self.root, "ppc64le")

    def test_next_linux_pilot_skips_only_with_paired_current_matching_pilot_evidence(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01", "supported_majors": [15, 18]},
                    "releases": [{"version": "15.9", "release_date": "2025-09-25"},
                                 {"version": "18.2", "release_date": "2025-09-25"}]}
        self.write("support/postgresql-releases.json", snapshot)
        checksum = "c" * 64
        passing_pair = [("18.2", endpoint, checksum, "passed", "postgresql", "18.2",
                         "linux-x86_64") for endpoint in ("minimum", "current")]
        self.write_pilot_records(passing_pair)
        self.assertEqual(plan_work.select_next_linux_pilot(self.root)["postgresql_version"], "15.9")

        cases = {
            "single endpoint": passing_pair[:1],
            "different checksums": [passing_pair[0], ("18.2", "current", "d" * 64,
                "passed", "postgresql", "18.2", "linux-x86_64")],
            "failed outcome": [("18.2", endpoint, checksum, "failed", "postgresql", "18.2",
                "linux-x86_64") for endpoint in ("minimum", "current")],
            "unrelated component": [("18.2", endpoint, checksum, "passed", "example", "18.2",
                "linux-x86_64") for endpoint in ("minimum", "current")],
            "unrelated PostgreSQL version": [("18.2", endpoint, checksum, "passed", "postgresql", "15.9",
                "linux-x86_64") for endpoint in ("minimum", "current")],
            "unrelated platform": [("18.2", endpoint, checksum, "passed", "postgresql", "18.2",
                "linux-arm64") for endpoint in ("minimum", "current")],
        }
        for label, records in cases.items():
            with self.subTest(label=label):
                self.write_pilot_records(records)
                self.assertEqual(plan_work.select_next_linux_pilot(self.root)["postgresql_version"], "18.2")
        with self.subTest(label="stale profile"):
            self.write_pilot_records(passing_pair, stale=True)
            self.assertEqual(plan_work.select_next_linux_pilot(self.root)["postgresql_version"], "18.2")

        arm_pair = [("18.2", endpoint, checksum, "passed", "postgresql", "18.2",
                     "linux-arm64") for endpoint in ("minimum", "current")]
        self.write_pilot_records(arm_pair, architecture="arm64")
        self.assertEqual(plan_work.select_next_linux_pilot(self.root, "arm64")["postgresql_version"], "15.9")

    def test_generic_pilot_selector_uses_declared_platform_and_current_macos_record(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01", "supported_majors": [15, 18]},
                    "releases": [{"version": "15.9", "release_date": "2025-09-25"},
                                 {"version": "18.2", "release_date": "2025-09-25"}]}
        self.write("support/postgresql-releases.json", snapshot)
        self.assertEqual(plan_work.select_pilot(self.root, "18.2", "macos-arm64"), {
            "postgresql_version": "18.2", "platform": "macos-arm64",
            "work": "build_missing", "snapshot_as_of": "2026-01-01"})
        self.assertEqual(plan_work.select_next_pilot(self.root, "macos-arm64")["postgresql_version"], "18.2")

        source = self.root / "tests/fixture.sh"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("suite", encoding="utf-8")
        self.write("support/verification-profiles.json", {"schema_version": 1, "profiles": {
            "fixture-macos": {"scope": "pilot-smoke", "platforms": ["macos-arm64"],
                              "case_ids": ["case-a"], "sources": ["tests/fixture.sh"]}}})
        profile = plan_work.coverage.verification_profile(self.root, "fixture-macos")
        record = {"schema_version": 2, "scope": "pilot-smoke", "profile_id": "fixture-macos",
                  "profile_revision": profile["profile_revision"], "outcome": "passed",
                  "sha256": "c" * 64, "component": "postgresql", "version": "18.2",
                  "platform": "macos-arm64", "postgresql_version": "18.2",
                  "test_revision": "a" * 40, "test_cases": profile["case_ids"],
                  "environment": {"os": "macos", "architecture": "arm64", "os_version": "15",
                                  "clean_system": True, "endpoint": "current", "image_id": "runner-image",
                                  "dependency_check_profile": "macho-system-dependencies-v1",
                                  "dependency_checks_passed": True}}
        self.write("support/verification/record.json", record)
        self.assertEqual(plan_work.select_next_pilot(self.root, "macos-arm64")["postgresql_version"], "15.9")
        source.write_text("changed suite", encoding="utf-8")
        self.assertEqual(plan_work.select_next_pilot(self.root, "macos-arm64")["postgresql_version"], "18.2")
        with self.assertRaisesRegex(plan_work.coverage.CoverageError, "undeclared pilot platform"):
            plan_work.select_next_pilot(self.root, "windows-arm64")


if __name__ == "__main__":
    unittest.main()
