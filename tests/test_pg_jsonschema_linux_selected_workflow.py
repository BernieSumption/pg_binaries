from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pg-jsonschema-linux-selected-publication.yml"
SELECTED_LINUX_WORKFLOWS = (
    "pgivm-linux-selected-publication.yml",
    "collection-linux-selected-publication.yml",
    "postgresql-linux-selected-publication.yml",
    "pgcron-linux-selected-publication.yml",
    "hypopg-linux-selected-publication.yml",
    "postgis-linux-selected-publication.yml",
    "pgaudit-linux-selected-publication.yml",
    "pgtap-linux-selected-publication.yml",
    "pgvector-linux-selected-publication.yml",
    "pg-jsonschema-linux-selected-publication.yml",
    "tiger-linux-selected-publication.yml",
)


class SelectedLinuxWorkflowTests(unittest.TestCase):
    def test_target_is_required_for_direct_dispatch(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('test -n "$POSTGRESQL_VERSION"', workflow)
        self.assertIn('test -n "$REQUESTED_ARCHITECTURE"', workflow)

    def test_workflow_plans_requested_target_and_reuses_existing_recipe(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tools/extension_archive_plan.py", workflow)
        self.assertIn("--project pg_jsonschema", workflow)
        self.assertNotIn('linux-publication.yml "linux-publication-$PG_ARCHITECTURE-evidence"', workflow)
        self.assertIn("scripts/pg_jsonschema/linux-build.sh", workflow)
        self.assertIn("PG_JSONSCHEMA_VERSION: ${{ needs.select.outputs.extension_version }}", workflow)
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
        self.assertNotIn('linux-publication.yml "linux-publication-$PG_ARCHITECTURE-evidence"', workflow)
        self.assertIn("scripts/pg_jsonschema/linux-verify.sh", workflow)

    def test_emitter_uses_transferred_core_resolution(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        emitter = (ROOT / "tools/emit_pg_jsonschema_linux_publication.py").read_text(encoding="utf-8")
        self.assertIn("scripts/linux/resolve-core.sh", workflow)
        self.assertNotIn("actions_candidate_discovery.py", workflow)
        self.assertIn("tools/linux_core_pin.py", (ROOT / "scripts/linux/resolve-core.sh").read_text(encoding="utf-8"))
        self.assertIn("--core-resolution", workflow)
        self.assertIn("linux_core_resolution.validate_resolution", emitter)

    def test_linux_recipe_uses_central_license_pointer(self):
        build = (ROOT / "scripts/pg_jsonschema/linux-build-in-container.sh").read_text()
        verify = (ROOT / "scripts/pg_jsonschema/linux-verify-in-container.sh").read_text()
        build_dockerfile = (ROOT / "scripts/pg_jsonschema/linux-build.Dockerfile").read_text()
        verify_dockerfile = (ROOT / "scripts/pg_jsonschema/linux-verify.Dockerfile").read_text()
        self.assertIn("license_pointer.py write", build)
        self.assertIn("license_pointer.py verify", verify)
        self.assertIn("tools/license_pointer.py", build_dockerfile)
        self.assertIn("tools/license_pointer.py", verify_dockerfile)
        for content in (build, verify, build_dockerfile, verify_dockerfile):
            self.assertNotIn("inventory_cargo_licenses", content)
            self.assertNotIn("component_inventory", content)

    def test_selected_linux_run_blocks_do_not_end_with_a_continuation(self):
        for filename in SELECTED_LINUX_WORKFLOWS:
            workflow = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
            lines = workflow.splitlines()
            for index, line in enumerate(lines):
                if line.strip() != "run: |":
                    continue
                indent = len(line) - len(line.lstrip())
                block = []
                for body_line in lines[index + 1:]:
                    if body_line.strip() and len(body_line) - len(body_line.lstrip()) <= indent:
                        break
                    block.append(body_line)
                final_command = next((line.rstrip() for line in reversed(block) if line.strip()), "")
                with self.subTest(workflow=filename, run_line=index + 1):
                    self.assertFalse(final_command.endswith("\\"), final_command)


if __name__ == "__main__":
    unittest.main()
