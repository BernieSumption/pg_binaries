from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/collection-macos-selected-publication.yml"


class CollectionMacosSelectedWorkflowTests(unittest.TestCase):
    def test_build_and_verify_shell_scripts_parse(self):
        scripts = [ROOT / "scripts/collection/build-macos.sh",
                   ROOT / "scripts/collection/verify-macos.sh"]
        subprocess.run(["bash", "-n", *map(str, scripts)], check=True)

    def test_selected_workflow_resolves_builds_and_verifies_one_target(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("workflow_call:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("tools/select_extension_work.py", workflow)
        self.assertIn("tools/collection_macos_targets/${POSTGRESQL_VERSION}-${ARCHITECTURE}.json", workflow)
        self.assertIn("scripts/macos/resolve-core.sh", workflow)
        self.assertIn("scripts/collection/build-macos.sh", workflow)
        self.assertIn("scripts/collection/verify-macos.sh", workflow)
        self.assertIn("needs: [select, build]", workflow)
        self.assertIn("actions/download-artifact@v4", workflow)
        self.assertIn("scripts/collection/probe.sql", (ROOT / "scripts/collection/verify-macos.sh").read_text())

    def test_both_release_outputs_and_evidence_paths_are_retained(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("collection 1.1.1 and 2.1.3", workflow)
        self.assertIn("collection-verification/publication/**", workflow)
        self.assertIn("support/evidence/collection-macos-publication-${{ github.run_id }}", workflow)
        self.assertIn("support/verification/collection-*", workflow)
        self.assertIn("steps.evidence.outcome", workflow)
        self.assertIn("steps.import.outcome", workflow)
        self.assertNotIn("push:", workflow)


if __name__ == "__main__":
    unittest.main()
