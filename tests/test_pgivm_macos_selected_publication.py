import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import emit_pgivm_macos_publication as publication


class PgIvmSelectedMacosPublicationTests(unittest.TestCase):
    def test_build_and_verify_shell_scripts_parse(self):
        scripts = [ROOT / "scripts/pg_ivm/macos-build-publication.sh",
                   ROOT / "scripts/pg_ivm/macos-verify-publication.sh"]
        subprocess.run(["bash", "-n", *map(str, scripts)], check=True)

    def test_target_configuration_covers_both_architectures_and_postgresql_releases(self):
        original = (publication.PROFILE_ID, publication.PG_VERSION,
                    publication.ARCHITECTURE, publication.PLATFORM,
                    publication.CORE_SHA256)
        try:
            for version in ("15.19", "16.15", "17.11", "18.6"):
                for architecture in ("arm64", "x86_64"):
                    with self.subTest(version=version, architecture=architecture), tempfile.TemporaryDirectory() as temp:
                        target = Path(temp) / "target.json"
                        digest = "a" * 64
                        target.write_text(json.dumps({
                            "postgresql_version": version,
                            "architecture": architecture,
                            "platform": f"macos-{architecture}",
                            "core_archive": {
                                "basename": f"postgresql-{version}-macos-{architecture}.tar.gz",
                                "sha256": digest,
                            },
                        }))
                        publication.configure_target(target)
                        self.assertEqual(publication.PG_VERSION, version)
                        self.assertEqual(publication.ARCHITECTURE, architecture)
                        self.assertEqual(publication.PLATFORM, f"macos-{architecture}")
                        self.assertEqual(publication.CORE_SHA256, digest)
                        self.assertEqual(publication.PROFILE_ID,
                                         f"pgivm-publication-macos-{architecture}-{version}")
        finally:
            (publication.PROFILE_ID, publication.PG_VERSION,
             publication.ARCHITECTURE, publication.PLATFORM,
             publication.CORE_SHA256) = original

    def test_target_configuration_rejects_unselected_or_unbound_target(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "target.json"
            target.write_text(json.dumps({
                "postgresql_version": "14.11", "architecture": "arm64",
                "platform": "macos-arm64", "core_archive": {
                    "basename": "postgresql-14.11-macos-arm64.tar.gz", "sha256": "a" * 64,
                },
            }))
            with self.assertRaisesRegex(Exception, "resolver target"):
                publication.configure_target(target)

    def test_postgresql_17_11_probe_output_is_checked_against_selected_version(self):
        original = (publication.PROFILE_ID, publication.PG_VERSION,
                    publication.ARCHITECTURE, publication.PLATFORM,
                    publication.CORE_SHA256)
        try:
            with tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / "target.json"
                target.write_text(json.dumps({
                    "postgresql_version": "17.11", "architecture": "x86_64",
                    "platform": "macos-x86_64", "core_archive": {
                        "basename": "postgresql-17.11-macos-x86_64.tar.gz",
                        "sha256": "b" * 64,
                    },
                }))
                publication.configure_target(target)
                probe = (
                    " postgres_version \n------------------\n 17.11\n(1 row)\n"
                    "CREATE EXTENSION\nCREATE TABLE\ncreate_immv\nDO\nDO\nDO\n"
                )
                publication._validate_probe_output(probe)
                with self.assertRaisesRegex(Exception, "selected PostgreSQL version"):
                    publication._validate_probe_output(probe.replace("17.11", "18.6"))
        finally:
            (publication.PROFILE_ID, publication.PG_VERSION,
             publication.ARCHITECTURE, publication.PLATFORM,
             publication.CORE_SHA256) = original

    def test_selected_workflow_verifies_both_cases_on_a_separate_runner_job(self):
        workflow = (ROOT / ".github/workflows/pgivm-macos-selected-publication.yml").read_text()
        self.assertIn("verify:\n    needs: [select, build]", workflow)
        self.assertIn("id: static_analysis", workflow)
        self.assertIn("id: archive_suite", workflow)
        self.assertIn("macos-15-intel", workflow)
        self.assertIn("macos-15", workflow)
        self.assertIn("scripts/macos/resolve-core.sh", workflow)
        self.assertIn('--archives "$RUNNER_TEMP/pgivm/verification"', workflow)
        self.assertIn('--pgivm-artifact "$RUNNER_TEMP/pgivm/verification"', workflow)

    def test_selected_workflow_derives_versions_from_declared_work(self):
        workflow = (ROOT / ".github/workflows/pgivm-macos-selected-publication.yml").read_text()
        self.assertIn("type: string\n      extension_version:", workflow)
        self.assertNotIn("options: ['17.11', '18.6']", workflow)
        self.assertNotIn("work.get('version') != '1.16'", workflow)
        self.assertNotIn("work.get('postgresql_version') != pg", workflow)
        self.assertIn("version != requested_version", workflow)
        self.assertIn("pg != requested_pg", workflow)
        self.assertIn("out.write(f'postgresql_version={pg}\\nextension_version={version}", workflow)
        self.assertIn("pg_ivm-${{ needs.select.outputs.extension_version }}-postgresql-", workflow)


if __name__ == "__main__":
    unittest.main()
