import json
import unittest
from pathlib import Path
import stat


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = (ROOT / ".github/workflows/selected-extension-publication.yml").read_text()
HYPOPG = (ROOT / ".github/workflows/hypopg-linux-selected-publication.yml").read_text()
PG_JSONSCHEMA_WINDOWS = (ROOT / ".github/workflows/pg-jsonschema-windows-selected-publication.yml").read_text()


class SelectedExtensionWorkflowTests(unittest.TestCase):
    def test_dispatcher_accepts_exact_request_with_scoped_branch_trial(self):
        self.assertIn("workflow_dispatch:", DISPATCHER)
        self.assertIn("workflow_call:", DISPATCHER)
        self.assertIn("  push:\n    branches: [spike]\n    paths:\n      - experiments/selected-extension-target-trial/request.json", DISPATCHER)
        self.assertNotIn("experiments/selected-extension-dispatch-trial", DISPATCHER)
        self.assertIn("tools/extension_archive_plan.py", DISPATCHER)
        self.assertNotIn("tools/dispatch_plan.py", DISPATCHER)
        self.assertNotIn("pgvector_checked_dispatch.sh", DISPATCHER)
        self.assertNotIn("hypopg_checked_dispatch.sh", DISPATCHER)
        self.assertNotIn("retry:", DISPATCHER)
        self.assertIn('(\"should_dispatch\", \"true\")', DISPATCHER)
        self.assertIn("needs.plan.outputs.should_dispatch == 'true'", DISPATCHER)
        self.assertIn("uses: ./.github/workflows/hypopg-linux-selected-publication.yml", DISPATCHER)
        self.assertIn("uses: ./.github/workflows/pgivm-linux-selected-publication.yml", DISPATCHER)
        self.assertIn("uses: ./.github/workflows/pgcron-linux-selected-publication.yml", DISPATCHER)
        self.assertIn('("pgaudit", "linux-x86_64"): "pgaudit-linux"', DISPATCHER)
        self.assertIn('("pgaudit", "linux-arm64"): "pgaudit-linux"', DISPATCHER)
        self.assertIn("uses: ./.github/workflows/pgaudit-linux-selected-publication.yml", DISPATCHER)
        self.assertIn('("PostGIS", "linux-x86_64"): "postgis-linux"', DISPATCHER)
        self.assertIn('("PostGIS", "linux-arm64"): "postgis-linux"', DISPATCHER)
        self.assertIn("uses: ./.github/workflows/postgis-linux-selected-publication.yml", DISPATCHER)
        self.assertIn('("PostGIS TIGER Geocoder", "linux-x86_64"): "tiger-linux"', DISPATCHER)
        self.assertIn('("PostGIS TIGER Geocoder", "linux-arm64"): "tiger-linux"', DISPATCHER)
        self.assertIn("uses: ./.github/workflows/tiger-linux-selected-publication.yml", DISPATCHER)
        self.assertIn('("pgvector", "linux-x86_64"): "pgvector-linux"', DISPATCHER)
        self.assertIn('("pgvector", "linux-arm64"): "pgvector-linux"', DISPATCHER)
        self.assertIn("uses: ./.github/workflows/pgvector-linux-selected-publication.yml", DISPATCHER)
        self.assertIn('("collection", "linux-x86_64"): "collection-linux"', DISPATCHER)
        self.assertIn('("collection", "linux-arm64"): "collection-linux"', DISPATCHER)
        self.assertIn("uses: ./.github/workflows/collection-linux-selected-publication.yml", DISPATCHER)
        self.assertIn("uses: ./.github/workflows/collection-macos-selected-publication.yml", DISPATCHER)
        self.assertIn("uses: ./.github/workflows/pgivm-macos-selected-publication.yml", DISPATCHER)

    def test_hypopg_checks_selected_dispatcher_candidates_first(self):
        self.assertIn("CALLER_WORKFLOW_REF: ${{ github.workflow_ref }}", HYPOPG)
        self.assertIn("*/.github/workflows/selected-extension-publication.yml@*", HYPOPG)
        self.assertIn('"hypopg-linux-$PG_VERSION-$PG_ARCHITECTURE-trial-{run_id}"', HYPOPG)
        self.assertIn('linux-changed-profiles.yml "hypopg-linux-core-', HYPOPG)
        self.assertIn('linux-changed-profiles.yml "postgresql-linux-selected-core-', HYPOPG)
        self.assertLess(HYPOPG.index('selected-extension-publication.yml "hypopg-linux-core-'),
                        HYPOPG.index('hypopg-linux-selected-publication.yml "hypopg-linux-core-'))
        self.assertNotIn("planner-dispatch-trial.yml", HYPOPG)

    def test_selected_linux_workflows_can_invoke_non_executable_recipes(self):
        for project in ("pgaudit", "postgis"):
            workflow = (ROOT / f".github/workflows/{project}-linux-selected-publication.yml").read_text()
            for phase in ("build", "verify"):
                script = ROOT / f"scripts/{project}/{phase}.sh"
                self.assertFalse(script.stat().st_mode & stat.S_IXUSR)
                self.assertIn(f"bash scripts/{project}/{phase}.sh", workflow)

    def test_pg_jsonschema_windows_workflow_uses_exact_inputs_and_selected_paths(self):
        self.assertIn("workflow_dispatch:", PG_JSONSCHEMA_WINDOWS)
        self.assertIn("workflow_call:", PG_JSONSCHEMA_WINDOWS)
        self.assertNotIn("  push:", PG_JSONSCHEMA_WINDOWS)
        self.assertNotIn("type: choice", PG_JSONSCHEMA_WINDOWS)
        self.assertIn("POSTGRESQL_VERSION: ${{ inputs.postgresql_version }}", PG_JSONSCHEMA_WINDOWS)
        self.assertIn("EXTENSION_VERSION: ${{ inputs.extension_version }}", PG_JSONSCHEMA_WINDOWS)
        self.assertNotIn("currently supports extension version 0.3.4", PG_JSONSCHEMA_WINDOWS)
        self.assertNotIn("'18.6'", PG_JSONSCHEMA_WINDOWS)
        self.assertNotIn("pg_jsonschema-0.3.4-postgresql-", PG_JSONSCHEMA_WINDOWS)

    def test_pg_jsonschema_windows_profiles_use_only_selected_workflow(self):
        profiles = json.loads((ROOT / "support/verification-profiles.json").read_text())["profiles"]
        for version in ("15.19", "16.15", "17.11", "18.6"):
            sources = profiles[f"pg-jsonschema-publication-windows-x86_64-{version}"]["sources"]
            self.assertIn(".github/workflows/pg-jsonschema-windows-selected-publication.yml", sources)
            self.assertNotIn(".github/workflows/pg-jsonschema-windows-publication.yml", sources)
        self.assertFalse((ROOT / ".github/workflows/pg-jsonschema-windows-publication.yml").exists())
        self.assertFalse((ROOT / ".github/workflows/pg-jsonschema-windows-feasibility.yml").exists())

    def test_address_standardizer_linux_routes_both_architectures(self):
        for platform in ("linux-x86_64", "linux-arm64"):
            self.assertIn(f'("Address Standardizer", "{platform}"): "address-standardizer-linux"', DISPATCHER)
        self.assertIn("uses: ./.github/workflows/address-standardizer-linux-selected-publication.yml", DISPATCHER)

    def test_pgcron_windows_routes_selected_postgresql_version(self):
        workflow = (ROOT / ".github/workflows/pgcron-windows-selected-publication.yml").read_text()
        self.assertIn('("pg_cron", "windows-x86_64"): "pgcron-windows"', DISPATCHER)
        self.assertIn("uses: ./.github/workflows/pgcron-windows-selected-publication.yml", DISPATCHER)
        self.assertIn("postgresql_version: ${{ needs.plan.outputs.postgresql_version }}", DISPATCHER)
        self.assertIn("extension_version: ${{ needs.plan.outputs.extension_version }}", DISPATCHER)
        self.assertIn("workflow_call:", workflow)
        self.assertIn("options: ['15.19', '16.15', '17.11', '18.6']", workflow)


if __name__ == "__main__":
    unittest.main()
