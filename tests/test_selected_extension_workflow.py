import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
