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
            "extensions": {"Example": {"sql_names": ["example"], "versions": {
                "1.0": {"postgresql_minimum_major": 15, "postgresql_maximum_major": 17}
            }}},
        }

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
        self.assertEqual(len(want_core), 6)
        self.assertEqual(len(want_extensions), 6)
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
        self.assertEqual(len(targets), 12)

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
                "extensions": {"Example": {"sql_names": ["example"], "versions": {
                    "1.0": {"postgresql_minimum_major": 19}
                }}},
            }
            snapshot = {"as_of": "2026-01-01", "source": "https://example.test/releases",
                        "releases": [{"version": "15.9", "release_date": "2025-09-25"}]}
            checksum = "a" * 64
            platforms = [f"{os}-{arch}" for os in ("macos", "windows", "linux")
                         for arch in ("x86_64", "arm64")]
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

            def run_cli():
                output = io.StringIO()
                with patch.object(sys, "argv", ["coverage.py", "--root", str(root)]), \
                        contextlib.redirect_stdout(output):
                    status = coverage.main()
                return status, output.getvalue()

            status, output = run_cli()
            self.assertEqual(status, 1)
            self.assertIn("core targets: 6 (6 missing)", output)
            self.assertIn("verification: unverified", output)

            records_dir = root / "support" / "verification"
            records_dir.mkdir(parents=True)
            record = {"outcome": "skipped", "sha256": checksum, "component": "postgresql",
                      "version": "15.9", "platform": "linux-arm64", "postgresql_version": "15.9",
                      "test_revision": "abc123", "environment": {"os_version": "5.15", "clean_system": True,
                      "endpoint": "minimum"}, "test_cases": ["smoke"]}
            record_path = records_dir / "postgres.json"
            record_path.write_text(json.dumps(record), encoding="utf-8")
            status, output = run_cli()
            self.assertEqual(status, 1)
            self.assertIn("core targets: 6 (6 missing)", output)
            self.assertIn("verification: incomplete", output)

            record["outcome"] = "passed"
            record_path.write_text(json.dumps(record), encoding="utf-8")
            status, output = run_cli()
            self.assertEqual(status, 1)
            self.assertIn("core targets: 6 (6 missing)", output)
            self.assertIn("verification: incomplete", output)

            record["environment"]["endpoint"] = "current"
            for platform in platforms:
                for endpoint in ("minimum", "current"):
                    copy = dict(record, platform=platform,
                                environment=dict(record["environment"], endpoint=endpoint))
                    path = records_dir / f"{platform}-{endpoint}.json"
                    path.write_text(json.dumps(copy), encoding="utf-8")
            status, output = run_cli()
            self.assertEqual(status, 0)
            self.assertIn("core targets: 6 (0 missing)", output)
            self.assertIn("verification: structural-only", output)

    def test_support_schema_requires_all_platforms_and_extensions(self):
        with self.assertRaises(coverage.CoverageError):
            coverage.validate_support({"schema_version": 2})
        incomplete = dict(self.support)
        incomplete["os_support"] = {"linux": {"minimum_version": "5.15"}}
        with self.assertRaises(coverage.CoverageError):
            coverage.validate_support(incomplete)

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
            record = {"outcome": "passed", "sha256": "a" * 64, "component": "postgresql",
                      "version": "15.9", "platform": "linux-arm64", "postgresql_version": "15.9",
                      "test_revision": "abc123", "environment": "clean-linux", "test_cases": ["smoke"]}
            (records_dir / "invalid.json").write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(coverage.CoverageError):
                coverage.verification_records(Path(temporary))


if __name__ == "__main__":
    unittest.main()
