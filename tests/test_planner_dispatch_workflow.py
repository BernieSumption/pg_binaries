import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRIAL = (ROOT / ".github/workflows/planner-dispatch-trial.yml").read_text()
SELECTED = (ROOT / ".github/workflows/hypopg-linux-selected-publication.yml").read_text()
TARGET = json.loads((ROOT / "experiments/planner-dispatch-trial/target.json").read_text())


class PlannerDispatchWorkflowContractTests(unittest.TestCase):
    def test_trial_declares_exact_target(self):
        self.assertEqual(TARGET, {
            "project": "HypoPG",
            "version": "1.4.3",
            "postgresql_version": "17.11",
            "platform": "linux-x86_64",
            "retry": False,
        })

    def test_dispatch_is_scoped_read_only_and_uses_planner_outputs(self):
        for path in (
            "experiments/planner-dispatch-trial/target.json",
            "tools/dispatch_plan.py",
            "tools/extension_work_queue.py",
            ".github/workflows/hypopg-linux-selected-publication.yml",
        ):
            self.assertIn(f"'{path}'", TRIAL)
        self.assertIn("actions: read", TRIAL)
        self.assertIn("contents: read", TRIAL)
        self.assertIn("python3 tools/dispatch_plan.py --request", TRIAL)
        self.assertIn("supports only HypoPG on linux-x86_64 or linux-arm64", TRIAL)
        self.assertIn("needs.plan.outputs.should_dispatch == 'true'", TRIAL)
        self.assertIn("uses: ./.github/workflows/hypopg-linux-selected-publication.yml", TRIAL)
        self.assertIn("needs.plan.outputs.postgresql_version", TRIAL)
        self.assertIn("needs.plan.outputs.extension_version", TRIAL)
        self.assertIn("needs.plan.outputs.platform == 'linux-arm64'", TRIAL)

    def test_selected_workflow_accepts_exact_reusable_inputs_without_duplicate_trial_push(self):
        self.assertIn("workflow_call:", SELECTED)
        for name in ("postgresql_version", "architecture", "extension_version"):
            self.assertIn(f"      {name}:\n", SELECTED)
        self.assertNotIn("experiments/planner-dispatch-trial/target.json", SELECTED)
        self.assertNotIn(".github/workflows/hypopg-linux-selected-publication.yml", SELECTED)
        self.assertIn("CALLER_WORKFLOW_REF: ${{ github.workflow_ref }}", SELECTED)
        self.assertIn("*/.github/workflows/planner-dispatch-trial.yml@*", SELECTED)
        self.assertIn("planner-dispatch-trial.yml", SELECTED)
        self.assertIn('"hypopg-linux-$PG_VERSION-$PG_ARCHITECTURE-trial-{run_id}"', SELECTED)


if __name__ == "__main__":
    unittest.main()
