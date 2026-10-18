import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PgCronMacOSFeasibilityTests(unittest.TestCase):
    def test_workflow_uses_named_standard_runner_and_exact_core_run(self):
        workflow = (ROOT / ".github/workflows/pgcron-macos-arm64-feasibility.yml").read_text()
        self.assertIn("runs-on: macos-15", workflow)
        self.assertIn("name: macos-arm64-pilot-archives", workflow)
        self.assertIn("run-id: 39079982683", workflow)
        self.assertNotIn("scripts/macos/build.sh", workflow)

    def test_script_pins_core_and_upstream_source_then_checks_behaviour(self):
        script = (ROOT / "scripts/pg_cron/macos-feasibility.sh").read_text()
        self.assertIn("bc543b0d54a8a33b3b737eab74d7f185035f01e5c2db4eb48be049996eee4440", script)
        self.assertIn("github-39079982683-1", script)
        self.assertIn("c19ab9bb35406c60fb51ecda993737c083850abe424acb6c1030439d00a1f8e4", script)
        self.assertRegex(script, re.compile(r"make PG_CONFIG=\"\$pg_config\" install DESTDIR="))
        self.assertIn("mv \"$pgroot\" \"$work/moved/postgresql\"", script)
        self.assertIn("CREATE EXTENSION pg_cron", script)
        self.assertIn("cron.use_background_workers=on", script)
        self.assertIn('[[ "$status" == succeeded ]]', script)
        self.assertIn("static_analysis.py", script)


if __name__ == "__main__":
    unittest.main()
