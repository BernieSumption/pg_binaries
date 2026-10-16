import importlib.util
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "coverage", Path(__file__).resolve().parents[1] / "tools" / "coverage.py"
)
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.support = {
            "schema_version": 1,
            "postgresql": {"minimum_major": 15, "stable_release_cutoff": "2025-09-25"},
            "os_support": {"macos": {}, "windows": {}, "linux": {}},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"], "linux": ["x86_64", "arm64"]},
            "extensions": {"Example": {"sql_names": ["example"], "versions": {
                "1.0": {"postgresql_minimum_major": 15, "postgresql_maximum_major": 17}
            }}},
        }

    @staticmethod
    def add_profile(root, *, profile_id="fixture-linux", scope="pilot-smoke",
                    platforms=None, case_ids=None, source_text="fixture source"):
        root = Path(root)
        source = root / "tests" / "fixture.sh"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(source_text, encoding="utf-8")
        profiles = {profile_id: {"scope": scope,
                                 "platforms": sorted(platforms or [
                                     f"{os}-{arch}" for os in ("macos", "linux")
                                     for arch in ("x86_64", "arm64")
                                 ] + ["windows-x86_64"]),
                                 "case_ids": sorted(case_ids or ["case-a", "case-b"]),
                                 "sources": ["tests/fixture.sh"]}}
        registry = root / "support" / "verification-profiles.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({"schema_version": 1, "profiles": profiles}), encoding="utf-8")
        return coverage.verification_profile(root, profile_id)

    @staticmethod
    def add_profile_fields(record, profile):
        record.update({"schema_version": 2, "profile_id": profile["profile_id"],
                       "profile_revision": profile["profile_revision"], "scope": profile["scope"],
                       "test_cases": profile["case_ids"]})

    def test_release_snapshot_filters_old_majors_and_cutoff(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases", "releases": [
            {"version": "14.20", "release_date": "2025-10-01"},
            {"version": "15.8", "release_date": "2025-09-24"},
            {"version": "15.9", "release_date": "2025-09-25"},
            {"version": "18.0rc1", "release_date": "2026-01-01"},
        ]}
        self.assertEqual(coverage.release_snapshot(snapshot, self.support), ["15.9"])

    def test_duplicate_release_rejected(self):
        release = {"version": "15.9", "release_date": "2025-09-25"}
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test", "releases": [release, release]}
        with self.assertRaises(coverage.CoverageError):
            coverage.release_snapshot(snapshot, self.support)

    def test_ranges_must_cover_each_required_release(self):
        want_core, want_extensions = coverage.expected_targets(self.support, ["15.9"])
        self.assertEqual(len(want_core), 5)
        self.assertEqual(len(want_extensions), 5)
        inventory = {"postgresql": {}, "extensions": {"example": {"1.0": {"downloads": {
            "linux-x86_64": [{"postgresql_support": {"from": "15.0", "to": "15.8"},
                               "url": "https://example.test/a", "sha256": "a" * 64}]
        }}}}}
        have_core, have_extensions = coverage.inventory_targets(inventory)
        self.assertEqual(len(have_core), 0)
        self.assertFalse(any(name == "example" and
                             coverage.version_parts(lo, "test") <= coverage.version_parts("15.9", "test")
                             <= coverage.version_parts(hi, "test")
                             for name, _, lo, hi, _ in have_extensions))

    def test_extension_target_classification_uses_download_range_and_final_archive_sha(self):
        target = ("example", "1.0", "15.9", "linux-x86_64")
        missing_target = ("example", "1.0", "15.9", "linux-arm64")
        download = {"url": "https://example.test/archive.tar.gz", "sha256": "a" * 64}
        key = ("example", "1.0", "15.0", "16.9", "linux-x86_64")
        records = [{"schema_version": 1, "scope": "publication", "outcome": "passed", "sha256": "b" * 64, "component": "example",
                    "version": "1.0", "platform": "linux-x86_64", "postgresql_version": "15.0",
                      "environment": {"endpoint": "minimum", "os": "linux", "architecture": "x86_64"}}]

        without_download, awaiting = coverage.classify_extension_targets(
            [target, missing_target], {key: download}, records)

        self.assertEqual(without_download, [missing_target])
        self.assertEqual(awaiting, [target])

    def test_extension_os_subset_keeps_both_architectures_and_pg_range(self):
        self.support["extensions"]["Example"]["versions"]["1.0"] = {
            "postgresql_minimum_major": 16,
            "postgresql_maximum_major": 17,
            "operating_systems": ["linux"],
        }
        _, targets = coverage.expected_targets(self.support, ["15.9", "16.11", "17.7", "18.0"])
        self.assertEqual(targets, {
            ("example", "1.0", pg, platform)
            for pg in ("16.11", "17.7")
            for platform in ("linux-x86_64", "linux-arm64")
        })

    def test_extension_os_subset_rejects_empty_unknown_and_duplicate(self):
        self.support["os_support"] = {
            name: {"minimum_version": "1.0"} for name in ("macos", "windows", "linux")
        }
        policy = self.support["extensions"]["Example"]["versions"]["1.0"]
        for systems in ([], ["linx"], ["linux", "linux"], [42]):
            with self.subTest(systems=systems):
                policy["operating_systems"] = systems
                with self.assertRaises(coverage.CoverageError):
                    coverage.validate_support(self.support)

    def test_open_pg_range_includes_future_stable_major(self):
        policy = self.support["extensions"]["Example"]["versions"]["1.0"]
        policy.pop("postgresql_maximum_major")
        _, targets = coverage.expected_targets(self.support, ["18.0", "19.0"])
        self.assertEqual(len(targets), 10)

    def test_overlapping_ranges_rejected(self):
        item = {"url": "https://example.test/a", "sha256": "a" * 64,
                "postgresql_support": {"from": "15.0", "to": "16.9"}}
        inventory = {"postgresql": {}, "extensions": {"x": {"1": {"downloads": {
            "linux-x86_64": [item, dict(item, postgresql_support={"from": "16.0", "to": "17.9"})]
        }}}}}
        with self.assertRaises(coverage.CoverageError):
            coverage.inventory_targets(inventory)

    def test_cli_requires_matching_passed_verification_and_uses_declared_platforms(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            support = {
                "schema_version": 1,
                "postgresql": {"minimum_major": 15, "stable_release_cutoff": "2025-09-25"},
                "os_support": {"macos": {"minimum_version": "11.0"},
                               "windows": {"minimum_version": "10.0"},
                               "linux": {"minimum_version": "5.15"}},
                "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"], "linux": ["x86_64", "arm64"]},
                "extensions": {"Example": {"sql_names": ["example"], "versions": {
                    "1.0": {"postgresql_minimum_major": 19}
                }}},
            }
            snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                        "releases": [{"version": "15.9", "release_date": "2025-09-25"}]}
            checksum = "a" * 64
            platforms = [f"{os}-{arch}" for os, arches in support["platform_architectures"].items()
                         for arch in arches]
            inventory = {"postgresql": {"15.9": {"downloads": {
                platform: {"url": "https://example.test/postgres.tar.gz", "sha256": checksum}
                for platform in platforms
            }}}, "extensions": {}}
            for name, value in (("support.json", support),
                                ("support/postgresql-releases.json", snapshot),
                                ("inventory.json", inventory)):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf-8")
            policy_path = root / "policies" / "extensions.md"
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text("## Example — include\n", encoding="utf-8")

            def run_cli(json_output=False):
                output = io.StringIO()
                argv = ["coverage.py", "--root", str(root)] + (["--json"] if json_output else [])
                with patch.object(sys, "argv", argv), \
                        contextlib.redirect_stdout(output):
                    status = coverage.main()
                return status, output.getvalue()

            status, output = run_cli()
            self.assertEqual(status, 1)
            self.assertIn("core targets: 5 (5 missing)", output)
            self.assertIn("core: 0 without download, 5 awaiting verification", output)
            self.assertIn("verification: unverified", output)

            records_dir = root / "support" / "verification"
            records_dir.mkdir(parents=True)
            profile = self.add_profile(root)
            record = {"outcome": "skipped", "sha256": checksum, "component": "postgresql",
                      "version": "15.9", "platform": "linux-arm64", "postgresql_version": "15.9",
                      "test_revision": "a" * 40, "environment": {"os": "linux", "architecture": "arm64",
                      "os_version": "5.15", "clean_system": True,
                      "endpoint": "minimum", "image_id": "ubuntu@sha256:image",
                      "dependency_check_profile": "linux-runtime-v1", "dependency_checks_passed": True}}
            self.add_profile_fields(record, profile)
            record_path = records_dir / "postgres.json"
            record_path.write_text(json.dumps(record), encoding="utf-8")
            status, output = run_cli()
            self.assertEqual(status, 1)
            self.assertIn("core targets: 5 (5 missing)", output)
            self.assertIn("core: 0 without download, 5 awaiting verification", output)
            self.assertIn("verification: incomplete", output)
            self.assertIn("verification skipped: postgresql 15.9 PostgreSQL 15.9 linux-arm64", output)
            self.assertIn("checks: case-a, case-b", output)
            status, output = run_cli(json_output=True)
            report = json.loads(output)
            self.assertEqual(status, 1)
            skipped = report["verification_records_by_outcome"]["skipped"]
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0]["target"]["platform"], "linux-arm64")
            self.assertEqual(skipped[0]["checks"], ["case-a", "case-b"])
            self.assertEqual(report["core_awaiting_verification"],
                             [["15.9", platform] for platform in sorted(platforms)])

            record["outcome"] = "failed"
            record_path.write_text(json.dumps(record), encoding="utf-8")
            status, output = run_cli(json_output=True)
            report = json.loads(output)
            self.assertEqual(status, 1)
            self.assertEqual(len(report["verification_records_by_outcome"]["failed"]), 1)
            self.assertEqual(report["verification_records_by_outcome"]["skipped"], [])
            self.assertEqual(report["core_awaiting_verification"],
                             [["15.9", platform] for platform in sorted(platforms)])

            record["outcome"] = "passed"
            record_path.write_text(json.dumps(record), encoding="utf-8")
            status, output = run_cli()
            self.assertEqual(status, 1)
            self.assertIn("core targets: 5 (5 missing)", output)
            self.assertIn("verification: incomplete", output)

            record["environment"]["endpoint"] = "current"
            profile = self.add_profile(root, scope="publication")
            self.add_profile_fields(record, profile)
            record_path.unlink()
            for platform in platforms:
                os_name, architecture = platform.split("-", 1)
                minimum = support["os_support"][os_name]["minimum_version"]
                current = {"macos": "12", "windows": "11", "linux": "6"}[os_name]
                for endpoint in ("minimum", "current"):
                    os_version = minimum if endpoint == "minimum" else current
                    copy = dict(record, platform=platform,
                                environment=dict(record["environment"], os=os_name,
                                                 architecture=architecture, os_version=os_version,
                                                 endpoint=endpoint))
                    path = records_dir / f"{platform}-{endpoint}.json"
                    path.write_text(json.dumps(copy), encoding="utf-8")
            status, output = run_cli()
            self.assertEqual(status, 0)
            self.assertIn("core targets: 5 (0 missing)", output)
            self.assertIn("verification: structural-only", output)

            inventory["postgresql"]["15.9"]["downloads"].pop("linux-arm64")
            (root / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
            output = io.StringIO()
            with patch.object(sys, "argv", ["coverage.py", "--root", str(root), "--json"]), \
                    contextlib.redirect_stdout(output):
                status = coverage.main()
            report = json.loads(output.getvalue())
            self.assertEqual(status, 1)
            self.assertEqual(report["core_without_download"], [["15.9", "linux-arm64"]])
            self.assertEqual(report["core_awaiting_verification"], [])
            self.assertEqual(report["missing_core"], report["core_without_download"])
            self.assertEqual(report["extension_without_download"], [])
            self.assertEqual(report["extension_awaiting_verification"], [])

    def test_support_schema_requires_all_platforms_and_extensions(self):
        with self.assertRaises(coverage.CoverageError):
            coverage.validate_support({"schema_version": 2})
        for pg_rule in ({"minimum_major": 16, "stable_release_cutoff": "2025-09-25"},
                        {"minimum_major": 15, "stable_release_cutoff": "2026-01-01"}):
            invalid = dict(self.support, postgresql=pg_rule)
            with self.assertRaises(coverage.CoverageError):
                coverage.validate_support(invalid)
        incomplete = dict(self.support)
        incomplete["os_support"] = {"linux": {"minimum_version": "5.15"}}
        with self.assertRaises(coverage.CoverageError):
            coverage.validate_support(incomplete)
        duplicate = dict(self.support, extensions={
            "Example": self.support["extensions"]["Example"],
            "Other": {"sql_names": ["example"], "versions": {"1.0": {}}},
        })
        with self.assertRaises(coverage.CoverageError):
            coverage.validate_support(duplicate)

    def test_extension_policy_includes_must_match_support_projects(self):
        with tempfile.TemporaryDirectory() as temporary:
            policy_dir = Path(temporary) / "policies"
            policy_dir.mkdir()
            policy_path = policy_dir / "extensions.md"
            policy_path.write_text(
                "## Example — include\n## Excluded — exclude\n## Unreviewed projects\n",
                encoding="utf-8",
            )
            coverage.validate_extension_policy(Path(temporary), self.support)

            policy_path.write_text(
                "## Example — include\n## Unreviewed projects\n"
                "| Project | SQL extension names | Upstream URL |\n"
                "| --- | --- | --- |\n| Example | `example` | URL |\n",
                encoding="utf-8",
            )
            with self.assertRaises(coverage.CoverageError):
                coverage.validate_extension_policy(Path(temporary), self.support)

            policy_path.write_text(
                "## Example — include\n## Other — exclude\n## Unreviewed projects\n"
                "| Project | SQL extension names | Upstream URL |\n"
                "| --- | --- | --- |\n| Other | `other` | URL |\n",
                encoding="utf-8",
            )
            with self.assertRaises(coverage.CoverageError):
                coverage.validate_extension_policy(Path(temporary), self.support)

            policy_path.write_text("## Other — include\n", encoding="utf-8")
            with self.assertRaises(coverage.CoverageError):
                coverage.validate_extension_policy(Path(temporary), self.support)

            policy_path.unlink()
            with self.assertRaises(coverage.CoverageError):
                coverage.validate_extension_policy(Path(temporary), self.support)
        incomplete = dict(self.support)
        incomplete["extensions"] = {}
        with self.assertRaises(coverage.CoverageError):
            coverage.validate_support(incomplete)

    def test_inventory_schema_rejects_non_object_records(self):
        with self.assertRaises(coverage.CoverageError):
            coverage.inventory_targets({"postgresql": {"15.9": []}, "extensions": {}})

    def test_verification_record_requires_structured_clean_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            records_dir = Path(temporary) / "support" / "verification"
            records_dir.mkdir(parents=True)
            self.add_profile(Path(temporary))
            record = {"schema_version": 2, "outcome": "passed", "sha256": "a" * 64, "component": "postgresql",
                      "version": "15.9", "platform": "linux-arm64", "postgresql_version": "15.9",
                      "profile_id": "fixture-linux", "profile_revision": "0" * 64,
                      "scope": "pilot-smoke", "test_revision": "a" * 40,
                      "environment": "clean-linux", "test_cases": ["smoke"]}
            (records_dir / "invalid.json").write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(coverage.CoverageError):
                coverage.verification_records(Path(temporary), self.support)

    def test_verification_record_binds_os_architecture_and_endpoint_version(self):
        self.support["os_support"] = {name: {"minimum_version": version} for name, version in
                                       (("macos", "11.0"), ("windows", "10.0"), ("linux", "5.15"))}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "support" / "verification"
            directory.mkdir(parents=True)
            profile = self.add_profile(root, platforms=["linux-x86_64"], case_ids=["case-a", "case-b"])
            record = {"outcome": "passed", "sha256": "a" * 64,
                      "component": "postgresql", "version": "15.9", "platform": "linux-x86_64",
                      "postgresql_version": "15.9", "test_revision": "a" * 40,
                      "environment": {"os": "linux", "architecture": "x86_64", "os_version": "5.15",
                                      "clean_system": True, "endpoint": "minimum", "image_id": "ubuntu@sha256:image",
                                      "dependency_check_profile": "linux-runtime-v1", "dependency_checks_passed": True}}
            self.add_profile_fields(record, profile)
            cases = [
                ("wrong-schema", {"schema_version": 1}, {}, "5.15", "minimum"),
                ("wrong-os", {}, {"os": "macos"}, "5.15", "minimum"),
                ("wrong-architecture", {}, {"architecture": "arm64"}, "5.15", "minimum"),
                ("minimum-too-new", {}, {}, "5.16", "minimum"),
                ("current-equal", {}, {}, "5.15", "current"),
                ("current-older", {}, {}, "5.14", "current"),
            ]
            for name, record_changes, environment_changes, version, endpoint in cases:
                with self.subTest(name=name):
                    environment = dict(record["environment"], **environment_changes,
                                       os_version=version, endpoint=endpoint)
                    (directory / "record.json").write_text(
                        json.dumps(dict(record, **record_changes, environment=environment)), encoding="utf-8")
                    with self.assertRaises(coverage.CoverageError):
                        coverage.verification_records(root, self.support)

    def test_profile_digest_and_exact_cases_reject_changed_or_forged_evidence(self):
        self.support["os_support"] = {name: {"minimum_version": "5.15"}
                                      for name in ("macos", "windows", "linux")}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "support" / "verification"
            directory.mkdir(parents=True)
            profile = self.add_profile(root, platforms=["linux-x86_64"])
            record = {"outcome": "passed",
                      "sha256": "a" * 64, "component": "postgresql", "version": "15.9",
                      "platform": "linux-x86_64", "postgresql_version": "15.9",
                      "test_revision": "a" * 40,
                      "environment": {"os": "linux", "architecture": "x86_64", "os_version": "5.15",
                                      "clean_system": True, "endpoint": "minimum", "image_id": "ubuntu@sha256:image",
                                      "dependency_check_profile": "linux-runtime-v1", "dependency_checks_passed": True}}
            self.add_profile_fields(record, profile)
            path = directory / "record.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            loaded = coverage.verification_records(root, self.support)
            download = {"sha256": "a" * 64}
            self.assertFalse(coverage.verified(loaded, download, "postgresql", "15.9",
                                               "linux-x86_64", "15.9", "minimum"))
            for changes in ({"outcome": "unknown"}, {"sha256": "bad"},
                            {"test_revision": "abc"}, {"test_cases": ["smoke", "smoke"]},
                            {"scope": "publication"}, {"profile_revision": "bad"},
                            {"environment": dict(record["environment"], image_id="")}):
                with self.subTest(changes=changes):
                    changed = dict(record, **{k: v for k, v in changes.items() if k != "environment"})
                    if "environment" in changes:
                        changed["environment"] = changes["environment"]
                    path.write_text(json.dumps(changed), encoding="utf-8")
                    with self.assertRaises(coverage.CoverageError):
                        coverage.verification_records(root, self.support)
            path.write_text(json.dumps(record), encoding="utf-8")
            first_revision = coverage.verification_profile(root, "fixture-linux")["profile_revision"]
            (root / "tests" / "fixture.sh").write_text("changed source", encoding="utf-8")
            changed_profile = coverage.verification_profile(root, "fixture-linux")
            self.assertNotEqual(first_revision, changed_profile["profile_revision"])
            stale_records = coverage.verification_records(root, self.support)
            self.assertEqual(len(stale_records), 1)
            self.assertFalse(stale_records[0]["_profile_current"])
            self.assertFalse(coverage.verified(stale_records, {"sha256": "a" * 64}, "postgresql",
                                               "15.9", "linux-x86_64", "15.9", "minimum"))
            (root / "tests" / "fixture.sh").write_text("fixture source", encoding="utf-8")
            registry_path = root / "support" / "verification-profiles.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["profiles"]["fixture-linux"]["case_ids"] = ["case-a", "case-b", "case-c"]
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            case_stale = coverage.verification_records(root, self.support)
            self.assertFalse(case_stale[0]["_profile_current"])
            (root / "tests" / "fixture.sh").unlink()
            missing_source = coverage.verification_records(root, self.support)
            self.assertFalse(missing_source[0]["_profile_current"])
            registry["profiles"].pop("fixture-linux")
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            removed_profile = coverage.verification_records(root, self.support)
            self.assertEqual(len(removed_profile), 1)
            self.assertFalse(removed_profile[0]["_profile_current"])
if __name__ == "__main__":
    unittest.main()
