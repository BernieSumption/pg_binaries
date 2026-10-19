import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pg-jsonschema-linux-selected-trial.yml"
TARGET = ROOT / "experiments/pg-jsonschema-linux-selected-trial/target.json"


class SelectedLinuxWorkflowTests(unittest.TestCase):
    def test_trial_target_is_a_supported_linux_target(self):
        target = json.loads(TARGET.read_text(encoding="utf-8"))
        releases = json.loads((ROOT / "support/postgresql-releases.json").read_text(encoding="utf-8"))
        versions = {row["version"] for row in releases["releases"]}
        self.assertIn(target["postgresql_version"], versions)
        self.assertIn(target["architecture"], {"x86_64", "arm64"})

    def test_workflow_plans_requested_target_and_reuses_existing_recipe(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tools/extension_archive_plan.py", workflow)
        self.assertIn("--project pg_jsonschema", workflow)
        self.assertIn("linux-publication-$PG_ARCHITECTURE-evidence", workflow)
        self.assertIn("scripts/pg_jsonschema/linux-build.sh", workflow)
        self.assertIn("scripts/pg_jsonschema/linux-verify.sh", workflow)
        self.assertIn("tools/emit_pg_jsonschema_linux_publication.py", workflow)
        self.assertIn("tools/import_pg_jsonschema_linux_publication.py", workflow)
        self.assertNotIn("--postgresql-version 17.11", workflow)

    def test_final_archive_is_verified_on_a_separate_runner_with_resolved_core(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("  build:\n", workflow)
        self.assertIn("  verify:\n", workflow)
        self.assertIn("needs: [select, build]", workflow)
        self.assertIn("Download final extension archive from the build job", workflow)
        self.assertIn("Download exact resolved PostgreSQL core archive", workflow)
        self.assertIn("Validate transferred core identity and provenance", workflow)
        self.assertIn("linux-publication-$PG_ARCHITECTURE-evidence", workflow)
        self.assertIn("scripts/pg_jsonschema/linux-verify.sh", workflow)

    def test_emitter_uses_transferred_core_resolution(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        emitter = (ROOT / "tools/emit_pg_jsonschema_linux_publication.py").read_text(encoding="utf-8")
        self.assertIn("scripts/linux/resolve-core.sh", workflow)
        self.assertIn("--core-resolution", workflow)
        self.assertIn("linux_core_resolution.validate_resolution", emitter)


if __name__ == "__main__":
    unittest.main()
