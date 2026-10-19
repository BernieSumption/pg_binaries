import unittest
from pathlib import Path
import stat


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = (ROOT / ".github/workflows/selected-extension-publication.yml").read_text()
HYPOPG = (ROOT / ".github/workflows/hypopg-linux-selected-publication.yml").read_text()


class SelectedExtensionWorkflowTests(unittest.TestCase):
    def test_dispatcher_accepts_exact_request_without_trial_push(self):
        self.assertIn("workflow_dispatch:", DISPATCHER)
        self.assertIn("workflow_call:", DISPATCHER)
        self.assertNotIn("  push:", DISPATCHER)
        self.assertNotIn("experiments/selected-extension-dispatch-trial", DISPATCHER)
        self.assertIn("python3 tools/dispatch_plan.py --request", DISPATCHER)
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
        self.assertIn("uses: ./.github/workflows/collection-macos-selected-publication.yml", DISPATCHER)
        self.assertIn("uses: ./.github/workflows/pgivm-macos-selected-publication.yml", DISPATCHER)

    def test_hypopg_checks_selected_dispatcher_candidates_first(self):
        self.assertIn("CALLER_WORKFLOW_REF: ${{ github.workflow_ref }}", HYPOPG)
        self.assertIn("*/.github/workflows/selected-extension-publication.yml@*", HYPOPG)
        self.assertIn('"hypopg-linux-$PG_VERSION-$PG_ARCHITECTURE-trial-{run_id}"', HYPOPG)
        self.assertIn('linux-changed-profiles.yml "hypopg-linux-core-', HYPOPG)
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


if __name__ == "__main__":
    unittest.main()
