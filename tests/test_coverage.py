import importlib.util
import contextlib
import hashlib
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
            "postgresql": {"minimum_major": 15},
            "version_selection_as_of": "2026-10-17",
            "os_support": {name: {"minimum_version": version} for name, version in
                           (("macos", "11.0"), ("windows", "10.0"), ("linux", "5.15"))},
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

    def test_release_snapshot_selects_latest_minor_of_supported_majors(self):
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                    "support_status": {"as_of": "2026-01-01", "source": "https://example.test/support",
                                       "supported_majors": [15]}, "releases": [
            {"version": "14.20", "release_date": "2025-10-01"},
            {"version": "15.8", "release_date": "2025-09-24"},
            {"version": "15.9", "release_date": "2025-09-25"},
            {"version": "18.0rc1", "release_date": "2026-01-01"},
        ]}
        self.assertEqual(coverage.release_snapshot(snapshot, self.support), ["15.9"])

    def test_duplicate_release_rejected(self):
        release = {"version": "15.9", "release_date": "2025-09-25"}
        snapshot = {"as_of": "2026-01-01", "source": "https://example.test",
                    "support_status": {"as_of": "2026-01-01", "source": "https://example.test/support",
                                       "supported_majors": [15]}, "releases": [release, release]}
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

    def test_extension_selection_uses_latest_compatible_release_per_major(self):
        support = json.loads(json.dumps(self.support))
        support["extensions"]["Example"]["versions"] = {
            "1.1": {"postgresql_maximum_major": 15},
            "1.2": {"postgresql_maximum_major": 15},
            "1.3": {"postgresql_minimum_major": 16},
            "2.0": {"postgresql_minimum_major": 15},
        }
        support["extensions"]["Example"]["major_first_releases"] = {
            "1": {"date": "2025-04-03", "source": "https://example.test/v1"},
            "2": {"date": "2026-03-20", "source": "https://example.test/v2"},
        }
        coverage.validate_support(support)
        _, targets = coverage.expected_targets(support, ["15.19", "16.15"])
        versions = {(version, pg) for _, version, pg, _ in targets}
        self.assertEqual(versions, {("1.2", "15.19"), ("2.0", "15.19"),
                                    ("1.3", "16.15"), ("2.0", "16.15")})

    def test_extension_major_ages_out_at_two_year_boundary(self):
        support = json.loads(json.dumps(self.support))
        support["extensions"]["Example"]["versions"]["2.0"] = {}
        support["extensions"]["Example"]["major_first_releases"] = {
            "1": {"date": "2024-10-17", "source": "https://example.test/v1"},
        }
        _, targets = coverage.expected_targets(support, ["15.19"])
        self.assertEqual({version for _, version, _, _ in targets}, {"1.0", "2.0"})
        support["version_selection_as_of"] = "2026-10-18"
        _, targets = coverage.expected_targets(support, ["15.19"])
        self.assertEqual({version for _, version, _, _ in targets}, {"2.0"})

    def test_extension_target_classification_verifies_selected_core_not_old_range_ends(self):
        target = ("example", "1.0", "15.9", "linux-x86_64")
        missing_target = ("example", "1.0", "15.9", "linux-arm64")
        download = {"url": "https://example.test/archive.tar.gz", "sha256": "a" * 64}
        key = ("example", "1.0", "15.0", "16.9", "linux-x86_64")
        core_downloads = {
            ("15.9", "linux-x86_64"): {"sha256": "b" * 64},
            ("15.0", "linux-x86_64"): {"sha256": "b" * 64},
            ("16.9", "linux-x86_64"): {"sha256": "c" * 64},
        }
        records = []
        for pg_version, core_sha256 in (("15.0", "b" * 64), ("16.9", "c" * 64)):
            for endpoint in ("minimum", "current"):
                records.append({
                    "scope": "publication", "outcome": "passed", "_profile_current": True,
                    "sha256": "a" * 64, "component": "example", "version": "1.0",
                    "platform": "linux-x86_64", "postgresql_version": pg_version,
                    "assembled_core": {"sha256": core_sha256},
                    "environment": {"endpoint": endpoint},
                })
        without_download, awaiting = coverage.classify_extension_targets(
            [target, missing_target], {key: download}, records, core_downloads)

        self.assertEqual(without_download, [missing_target])
        self.assertEqual(awaiting, [target])

        for endpoint in ("minimum", "current"):
            records.append({
                "scope": "publication", "outcome": "passed", "_profile_current": True,
                "sha256": "a" * 64, "component": "example", "version": "1.0",
                "platform": "linux-x86_64", "postgresql_version": "15.9",
                "assembled_core": {"sha256": "d" * 64},
                "environment": {"endpoint": endpoint},
            })
        records[-2]["assembled_core"]["sha256"] = "b" * 64
        without_download, awaiting = coverage.classify_extension_targets(
            [target], {key: download}, records, core_downloads)
        self.assertEqual(without_download, [])
        self.assertEqual(awaiting, [target])

        records[-1]["assembled_core"]["sha256"] = "b" * 64
        _, awaiting = coverage.classify_extension_targets(
            [target], {key: download}, records, core_downloads)
        self.assertEqual(awaiting, [])

        without_download, awaiting = coverage.classify_extension_targets(
            [target], {key: download}, records, {})
        self.assertEqual(without_download, [])
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
                "postgresql": {"minimum_major": 15},
                "version_selection_as_of": "2026-10-17",
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
                        "support_status": {"as_of": "2026-01-01", "source": "https://example.test/support", "supported_majors": [15]},
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
                      "os_version": "5.15", "clean_system": False,
                      "endpoint": "minimum", "image_id": "ubuntu@sha256:image",
                      "dependency_check_profile": "linux-runtime-v1", "dependency_checks_passed": False}}
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
            record["environment"]["clean_system"] = True
            record["environment"]["dependency_checks_passed"] = True
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
                for endpoint in ("current",):
                    os_version = minimum if endpoint == "minimum" else current
                    copy = dict(record, platform=platform,
                                environment=dict(record["environment"], os=os_name,
                                                 architecture=architecture, os_version=os_version,
                                                 endpoint=endpoint),
                                case_results={case: "passed" for case in record["test_cases"]})
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

    def test_support_validates_required_project_version_constraints(self):
        support = json.loads(json.dumps(self.support))
        support["extensions"] = {
            "PostGIS": {"sql_names": ["postgis"], "requires": [], "versions": {"3.5.7": {}, "3.6.4": {}}},
            "TIGER": {"sql_names": ["tiger"], "requires": ["PostGIS"],
                      "requires_versions": {"PostGIS": {"minimum_version": "3.6"}},
                      "versions": {"2025.2": {}}},
        }
        coverage.validate_support(support)
        for invalid in (
                {"PostGIS": {"minimum_version": "3.x"}},
                {"PostGIS": {"minimum_version": "9.0"}},
                {"PostGIS": {"minimum_version": "3.6", "maximum_version": "3.8"}},
                {"Unrequired": {"minimum_version": "3.6"}},
        ):
            with self.subTest(invalid=invalid):
                bad = json.loads(json.dumps(support))
                bad["extensions"]["TIGER"]["requires_versions"] = invalid
                with self.assertRaises(coverage.CoverageError):
                    coverage.validate_support(bad)

    def test_prerequisite_archive_resolution_applies_minimum_version(self):
        support = {
            "extensions": {
                "PostGIS": {"sql_names": ["postgis", "postgis_raster"], "versions": {"3.5.7": {}, "3.6.4": {}}},
                "TIGER": {"sql_names": ["tiger"], "requires": ["PostGIS"],
                          "requires_versions": {"PostGIS": {"minimum_version": "3.6"}},
                          "versions": {"2025.2": {}}},
            },
        }
        downloads = {}
        for name in ("postgis", "postgis_raster"):
            for version in ("3.5.7", "3.6.4"):
                key = (name, version, "18.6", "18.6", "linux-x86_64")
                downloads[key] = {"url": f"https://example.test/postgis-{version}.tar.gz",
                                  "sha256": ("a" if version == "3.5.7" else "b") * 64}
        result = coverage.expected_prerequisite_archives(support, downloads, "TIGER", "18.6", "linux-x86_64")
        self.assertEqual(result[0]["version"], "3.6.4")
        only_old = {key: value for key, value in downloads.items() if key[1] == "3.5.7"}
        self.assertIsNone(coverage.expected_prerequisite_archives(
            support, only_old, "TIGER", "18.6", "linux-x86_64"))

    def test_verification_record_rejects_old_prerequisite_archive_version(self):
        support = {
            "schema_version": 1, "postgresql": {"minimum_major": 15},
                "version_selection_as_of": "2026-10-17",
            "os_support": {name: {"minimum_version": version} for name, version in
                           (("macos", "11.0"), ("windows", "10.0"), ("linux", "5.15"))},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"macos": ["x86_64", "arm64"], "windows": ["x86_64"],
                                        "linux": ["x86_64", "arm64"]},
            "extensions": {
                "PostGIS": {"sql_names": ["postgis"], "requires": [], "versions": {"3.5.7": {}, "3.6.4": {}}},
                "PostGIS TIGER Geocoder": {"sql_names": ["postgis_tiger_geocoder"], "requires": ["PostGIS"],
                                           "requires_versions": {"PostGIS": {"minimum_version": "3.6"}},
                                           "versions": {"2025.2": {"postgresql_minimum_major": 16,
                                                                   "postgresql_maximum_major": 18}}},
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.add_profile(root, scope="publication", platforms=["linux-x86_64"],
                                       case_ids=["case-a"])
            record = {"schema_version": 2, "outcome": "passed", "sha256": "a" * 64,
                      "component": "postgis_tiger_geocoder", "project": "PostGIS TIGER Geocoder",
                      "version": "2025.2", "platform": "linux-x86_64", "postgresql_version": "18.6",
                      "test_revision": "b" * 40, "test_cases": ["case-a"],
                      "case_results": {"case-a": "passed"}, "scope": "publication",
                      "profile_id": profile["profile_id"], "profile_revision": profile["profile_revision"],
                      "assembled_core": {"archive": "postgresql-18.6-linux-x86_64.tar.gz",
                                         "version": "18.6", "sha256": "c" * 64},
                      "prerequisite_archives": [{"project": "PostGIS",
                          "archive": "postgis-3.5.7-postgresql-18.6-linux-x86_64.tar.gz",
                          "version": "3.5.7", "sha256": "d" * 64}],
                      "environment": {"os": "linux", "architecture": "x86_64", "os_version": "5.15",
                                      "clean_system": True, "endpoint": "minimum", "image_id": "test-image",
                                      "dependency_check_profile": "test", "dependency_checks_passed": True}}
            with self.assertRaisesRegex(coverage.CoverageError, "does not meet minimum 3.6"):
                coverage.validate_verification_record(record, support, root)
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
                ("unclean-pass", {}, {"clean_system": False}, "5.15", "minimum"),
                ("minimum-too-new", {}, {}, "5.16", "minimum"),
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

    def test_publication_records_require_complete_consistent_case_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.add_profile(root, scope="publication",
                                       platforms=["linux-x86_64"],
                                       case_ids=["case-a", "case-b"])
            record = {
                "outcome": "passed", "sha256": "a" * 64,
                "component": "postgresql", "version": "18.6",
                "platform": "linux-x86_64", "postgresql_version": "18.6",
                "test_revision": "b" * 40,
                "case_results": {"case-a": "passed", "case-b": "passed"},
                "environment": {
                    "os": "linux", "architecture": "x86_64", "os_version": "5.15",
                    "clean_system": True, "endpoint": "minimum", "image_id": "ubuntu@sha256:image",
                    "dependency_check_profile": "linux-runtime-v1", "dependency_checks_passed": True,
                },
            }
            self.add_profile_fields(record, profile)
            self.assertTrue(coverage.validate_verification_record(record, self.support, root))

            extension_record = dict(record, component="example", version="1.0",
                                    assembled_core={"archive": "postgresql-18.6-linux-x86_64.tar.gz",
                                                   "version": "18.6", "sha256": "c" * 64})
            self.assertTrue(coverage.validate_verification_record(extension_record, self.support, root))
            for assembled_core in (
                    None,
                    {"archive": "postgresql-18.6-linux-arm64.tar.gz", "version": "18.6",
                     "sha256": "c" * 64},
                    {"archive": "postgresql-18.6-linux-x86_64.tar.gz", "version": "18.5",
                     "sha256": "c" * 64},
                    {"archive": "postgresql-18.6-linux-x86_64.tar.gz", "version": "18.6",
                     "sha256": "bad"},
            ):
                with self.subTest(assembled_core=assembled_core):
                    with self.assertRaisesRegex(coverage.CoverageError, "requires assembled_core"):
                        coverage.validate_verification_record(
                            dict(extension_record, assembled_core=assembled_core), self.support, root)

            invalid_results = (
                {},
                {"case-a": "passed"},
                {"case-a": "passed", "case-b": "passed", "extra": "passed"},
                {"case-a": "passed", "case-b": "unknown"},
                {"case-a": "passed", "case-b": ["passed"]},
            )
            for results in invalid_results:
                with self.subTest(results=results):
                    with self.assertRaises(coverage.CoverageError):
                        coverage.validate_verification_record(
                            dict(record, case_results=results), self.support, root)

            for outcome, results in (
                ("failed", {"case-a": "failed", "case-b": "passed"}),
                ("skipped", {"case-a": "passed", "case-b": "skipped"}),
            ):
                with self.subTest(outcome=outcome):
                    failed_or_skipped = dict(record, outcome=outcome, case_results=results)
                    self.assertTrue(coverage.validate_verification_record(
                        failed_or_skipped, self.support, root))

            for outcome, results in (
                ("passed", {"case-a": "failed", "case-b": "passed"}),
                ("failed", {"case-a": "passed", "case-b": "passed"}),
                ("skipped", {"case-a": "failed", "case-b": "skipped"}),
            ):
                with self.subTest(outcome=outcome, results=results):
                    with self.assertRaises(coverage.CoverageError):
                        coverage.validate_verification_record(
                            dict(record, outcome=outcome, case_results=results),
                            self.support, root)

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

    def test_profile_digest_accepts_windows_checkout_line_endings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.add_profile(root, profile_id="fixture-windows",
                                       platforms=["windows-x86_64"],
                                       source_text="first\nsecond\n")
            source = root / "tests" / "fixture.sh"
            source.write_bytes(b"first\r\nsecond\r\n")
            windows_profile = coverage.verification_profile(root, "fixture-windows")
            self.assertEqual(profile["profile_revision"], windows_profile["profile_revision"])
            registry = json.loads((root / "support" / "verification-profiles.json").read_text())
            definition = registry["profiles"]["fixture-windows"]
            legacy_input = {"profile_id": "fixture-windows", "scope": definition["scope"],
                            "case_ids": definition["case_ids"], "platforms": definition["platforms"],
                            "sources": {"tests/fixture.sh": hashlib.sha256(source.read_bytes()).hexdigest()}}
            legacy_revision = hashlib.sha256(json.dumps(
                legacy_input, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False).encode("utf-8")).hexdigest()
            self.assertIn(legacy_revision, windows_profile["compatible_profile_revisions"])
            record = {"schema_version": 2, "profile_id": "fixture-windows",
                      "profile_revision": legacy_revision, "scope": "pilot-smoke",
                      "outcome": "passed", "sha256": "a" * 64, "test_revision": "a" * 40,
                      "test_cases": definition["case_ids"], "platform": "windows-x86_64",
                      "environment": {"os": "windows", "architecture": "x86_64",
                                      "image_id": "windows-test", "dependency_check_profile": "test",
                                      "dependency_checks_passed": True, "clean_system": True}}
            self.assertTrue(coverage.validate_verification_record(record, self.support, root))
            source.write_bytes(b"first\r\nchanged\r\n")
            changed = coverage.verification_profile(root, "fixture-windows")
            self.assertNotIn(legacy_revision, changed["compatible_profile_revisions"])
            self.assertFalse(coverage.validate_verification_record(
                record, self.support, root, allow_stale=True))
            source.write_bytes(b"\0first\r\n")
            binary_crlf = coverage.verification_profile(root, "fixture-windows")
            source.write_bytes(b"\0first\n")
            binary_lf = coverage.verification_profile(root, "fixture-windows")
            self.assertNotEqual(binary_crlf["profile_revision"], binary_lf["profile_revision"])

    @staticmethod
    def add_workflow_section_profile(root, source=".github/workflows/linux-publication.yml#profile-section=build"):
        root = Path(root)
        registry = root / "support" / "verification-profiles.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({"schema_version": 1, "profiles": {
            "fixture-workflow": {
                "scope": "publication",
                "platforms": ["linux-x86_64"],
                "case_ids": ["build"],
                "sources": [source],
            },
        }}), encoding="utf-8")

    def test_workflow_profile_section_hashes_only_execution_section(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.add_workflow_section_profile(root)
            workflow = root / ".github" / "workflows" / "linux-publication.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "name: Linux publication\n"
                "# profile-section: build begin\n"
                "run: ./verify.sh\n"
                "# profile-section: build end\n"
                "name: reporting\n",
                encoding="utf-8",
            )
            original = coverage.verification_profile(root, "fixture-workflow")

            workflow.write_text(
                "name: Updated Linux publication report\n"
                "# profile-section: build begin\n"
                "run: ./verify.sh\n"
                "# profile-section: build end\n"
                "name: updated reporting\n",
                encoding="utf-8",
            )
            reporting_edit = coverage.verification_profile(root, "fixture-workflow")
            self.assertEqual(original["profile_revision"], reporting_edit["profile_revision"])

            workflow.write_text(
                "name: Updated Linux publication report\n"
                "# profile-section: build begin\n"
                "run: ./verify-changed.sh\n"
                "# profile-section: build end\n"
                "name: updated reporting\n",
                encoding="utf-8",
            )
            execution_edit = coverage.verification_profile(root, "fixture-workflow")
            self.assertNotEqual(reporting_edit["profile_revision"], execution_edit["profile_revision"])

    def test_workflow_profile_section_normalizes_utf8_crlf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.add_workflow_section_profile(root)
            workflow = root / ".github" / "workflows" / "linux-publication.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_bytes(
                b"metadata\n# profile-section: build begin\nrun: ./verify.sh\n"
                b"# profile-section: build end\nreport\n"
            )
            lf_profile = coverage.verification_profile(root, "fixture-workflow")
            workflow.write_bytes(workflow.read_bytes().replace(b"\n", b"\r\n"))
            crlf_profile = coverage.verification_profile(root, "fixture-workflow")
            self.assertEqual(lf_profile["profile_revision"], crlf_profile["profile_revision"])

    def test_workflow_profile_section_rejects_missing_duplicate_and_reversed_markers(self):
        invalid_sections = {
            "missing begin": "# profile-section: build wrong\ncommand\n",
            "missing end": "# profile-section: build begin\ncommand\n",
            "duplicate begin": (
                "# profile-section: build begin\ncommand\n"
                "# profile-section: build begin\ncommand\n"
                "# profile-section: build end\n"
            ),
            "duplicate end": (
                "# profile-section: build begin\ncommand\n"
                "# profile-section: build end\n"
                "# profile-section: build end\n"
            ),
            "reversed": "# profile-section: build end\ncommand\n# profile-section: build begin\n",
        }
        for label, content in invalid_sections.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.add_workflow_section_profile(root)
                workflow = root / ".github" / "workflows" / "linux-publication.yml"
                workflow.parent.mkdir(parents=True)
                workflow.write_text(content, encoding="utf-8")
                with self.assertRaises(coverage.CoverageError):
                    coverage.verification_profile(root, "fixture-workflow")

    def test_workflow_profile_section_syntax_is_limited_to_publication_workflow(self):
        for source in (
            "tests/fixture.sh#profile-section=build",
            ".github/workflows/other.yml#profile-section=build",
            ".github/workflows/linux-publication.yml#other-fragment=build",
        ):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.add_workflow_section_profile(root, source=source)
                with self.assertRaises(coverage.CoverageError):
                    coverage.verification_profile(root, "fixture-workflow")

if __name__ == "__main__":
    unittest.main()
