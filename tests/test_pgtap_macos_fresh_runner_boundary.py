import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PgtapMacosFreshRunnerBoundaryTests(unittest.TestCase):
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
        workflow = (ROOT / ".github/workflows/pgtap-macos-arm64-selected-publication.yml").read_text()
        self.assertIn("  build:\n", workflow)
        self.assertIn("  verify:\n", workflow)
        self.assertIn("needs: [select, build]", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("actions/download-artifact@v4", workflow)
        self.assertIn("verify-macos-publication.sh static-analysis", workflow)
        self.assertIn("verify-macos-publication.sh archive-suite", workflow)


if __name__ == "__main__":
    unittest.main()
