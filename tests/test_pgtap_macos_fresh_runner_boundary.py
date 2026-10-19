import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PgtapMacosFreshRunnerBoundaryTests(unittest.TestCase):
    def _workflow_job(self, architecture, job):
        workflow = (ROOT / f".github/workflows/pgtap-macos-{architecture}-selected-publication.yml").read_text()
        marker = f"  {job}:\n"
        start = workflow.index(marker) + len(marker)
        end = len(workflow)
        for candidate in ("select", "build", "verify"):
            if candidate == job:
                continue
            position = workflow.find(f"  {candidate}:\n", start)
            if position >= 0:
                end = min(end, position)
        return workflow[start:end]

    def test_build_only_stops_after_archive_packaging_checks(self):
        script = (ROOT / "scripts/pgtap/macos-feasibility.sh").read_text()
        boundary = script.index('if [[ $build_only == --build-only ]]')
        self.assertGreater(boundary, script.index('shasum -a 256 -c "$extension_name.sha256"'))
        self.assertGreater(boundary, script.index('check_extension_redistribution.py'))
        self.assertLess(boundary, script.index('tar -xzf "$extension_name"'))
        self.assertLess(boundary, script.index('static_analysis.py'))
        self.assertLess(boundary, script.index('"$pgroot/bin/initdb"'))

    def test_verifier_consumes_archives_without_building_from_source(self):
        verifier = (ROOT / "scripts/pgtap/verify-macos-publication.sh").read_text()
        self.assertNotIn("curl", verifier)
        self.assertNotIn("make ", verifier)
        self.assertIn('shasum -a 256 -c "$core_name.sha256"', verifier)
        self.assertIn('shasum -a 256 -c "$extension_name.sha256"', verifier)
        self.assertIn('static_analysis.py', verifier)
        self.assertIn('scripts/pgtap/probe.sql', verifier)

    def test_selected_publication_verifies_uploaded_build_on_another_job(self):
        for architecture, runner, versions in (
            ("arm64", "macos-15", ("18.6",)),
            ("x86_64", "macos-15-intel", ("15.19", "16.15", "17.11", "18.6")),
        ):
            with self.subTest(architecture=architecture):
                path = ROOT / f".github/workflows/pgtap-macos-{architecture}-selected-publication.yml"
                workflow = path.read_text()
                select = self._workflow_job(architecture, "select")
                build = self._workflow_job(architecture, "build")
                verify = self._workflow_job(architecture, "verify")

                self.assertIn("needs: [select, build]", workflow)
                self.assertIn(f"runs-on: {runner}", build)
                self.assertIn(f"runs-on: {runner}", verify)
                self.assertIn("actions/upload-artifact@v4", build)
                self.assertIn("actions/download-artifact@v4", verify)
                build_name = next(line.split("name: ", 1)[1] for line in build.splitlines() if "name: pgtap-macos-" in line and "-build-" in line)
                download_name = next(line.split("name: ", 1)[1] for line in verify.splitlines() if "name: pgtap-macos-" in line and "-build-" in line)
                self.assertEqual(build_name, download_name)
                self.assertIn("verify-macos-publication.sh static-analysis", verify)
                self.assertIn("verify-macos-publication.sh archive-suite", verify)
                self.assertIn("scripts/macos/resolve-core.sh", build)
                self.assertIn("GH_TOKEN: ${{ github.token }}", build)
                self.assertIn('"$RUNNER_TEMP/core-archives/target.json" --build-only', build)
                self.assertIn('--target-config "$RUNNER_TEMP/core-archives/target.json"', verify)
                self.assertNotIn("core_run_id", workflow)
                self.assertNotIn("run-id:", workflow)

                self.assertIn(f"--platform macos-{architecture}", select)
                if architecture == "x86_64":
                    self.assertIn(f'${{POSTGRESQL_VERSION}}-{architecture}.json', select)
                else:
                    self.assertNotIn("pin_path", select)
                if architecture == "x86_64":
                    for version in versions:
                        self.assertTrue((ROOT / f"tools/pgtap_macos_pins/{version}-{architecture}.json").is_file())
                self.assertIn(f"support/evidence/pgtap-macos-publication-${{{{ github.run_id }}}}/{architecture}/**", verify)
                self.assertIn(f"-macos-{architecture}-current-", verify)

    def test_arm64_target_is_derived_from_selected_work_and_callable_by_dispatcher(self):
        workflow = (ROOT / ".github/workflows/pgtap-macos-arm64-selected-publication.yml").read_text()
        select = self._workflow_job("arm64", "select")
        self.assertIn("workflow_call:", workflow)
        self.assertIn("--postgresql-version \"$POSTGRESQL_VERSION\"", select)
        self.assertIn("work.get('version') != version", select)
        self.assertIn("work.get('postgresql_version') != pg", select)
        self.assertIn("version: ${{ steps.work.outputs.version }}", workflow)
        self.assertIn("pgtap-${{ needs.select.outputs.extension_version }}-postgresql-", workflow)
        self.assertNotIn("The selected pgTAP release is", select)
        self.assertNotIn("15.19|16.15|17.11|18.6", select)

        dispatcher = (ROOT / ".github/workflows/selected-extension-publication.yml").read_text()
        self.assertIn('(\"pgtap\", \"macos-arm64\"): \"pgtap-macos-arm64\"', dispatcher)
        self.assertIn("uses: ./.github/workflows/pgtap-macos-arm64-selected-publication.yml", dispatcher)


if __name__ == "__main__":
    unittest.main()
