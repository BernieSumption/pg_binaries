"""Exercise HypoPG macOS archive binding against the PostgreSQL 17.11 target."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import emit_hypopg_macos_publication as emitter
from hypopg_macos_target import load_target_config
from test_emit_hypopg_macos_publication import HypoPGMacOSFixture


class HypoPGMacOS1711Arm64Tests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.target = load_target_config(root / "tools/hypopg_macos_pins/17.11-arm64.json")
        self.fixture = HypoPGMacOSFixture(self.target)
        self.addCleanup(self.fixture.close)

    def test_config_is_pinned_to_imported_core_and_profile(self):
        root = Path(__file__).resolve().parents[1]
        pin = json.loads((root / "tools/hypopg_macos_pins/17.11-arm64.json").read_text())
        profile = json.loads((root / "support/verification-profiles.json").read_text())[
            "profiles"][self.target.profile_id]
        self.assertEqual(pin["core_archive"]["run_id"], "39093804725")
        self.assertEqual(pin["core_archive"]["build_id"], "github-39093804725-1")
        self.assertEqual(pin["core_archive"]["sha256"],
                         "d9ac809946cd87bbb585135d0ff329d33d5563047b9caaa312aea9116a8d9eaa")
        self.assertEqual(profile["scope"], "publication")
        self.assertEqual(profile["platforms"], ["macos-arm64"])
        self.assertIn("tools/hypopg_macos_target.py", profile["sources"])
        self.assertIn("scripts/hypopg/macos-feasibility.sh", profile["sources"])
        self.assertIn("scripts/hypopg/verify-macos-publication.sh", profile["sources"])
        self.assertIn("policies/install-process.md", profile["sources"])

    def test_publication_verifies_uploaded_archives_in_a_separate_runner_job(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/hypopg-macos-arm64-selected-publication.yml").read_text()
        verifier = (root / "scripts/hypopg/verify-macos-publication.sh").read_text()
        installer_policy = (root / "policies/install-process.md").read_text()
        profile = json.loads((root / "support/verification-profiles.json").read_text())["profiles"][
            self.target.profile_id]

        self.assertIn("  build:\n", workflow)
        self.assertIn("  verify:\n    needs: [select, build]", workflow)
        self.assertIn("runs-on: macos-15", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("actions/download-artifact@v4", workflow)
        self.assertIn("verify-macos-publication.sh static-analysis", workflow)
        self.assertIn("verify-macos-publication.sh archive-suite", workflow)
        self.assertIn("if: always() && steps.download.outcome == 'success'", workflow)
        self.assertIn("if [[ -f \"$RUNNER_TEMP/hypopg-publication/publication/attempt.json\" ]]", workflow)
        self.assertIn("--run-id \"$GITHUB_RUN_ID\"", workflow)
        self.assertIn("scripts/hypopg/verify-macos-publication.sh", profile["sources"])
        self.assertIn("policies/install-process.md", profile["sources"])
        self.assertIn("copy the contents of the project-named payload directory", installer_policy)
        self.assertIn("cp -a \"$extroot/.\" \"$pgroot/\"", verifier)
        self.assertIn('mv "$pgroot" "$work/moved/postgresql"', verifier)
        self.assertIn("static_analysis.py", verifier)
        self.assertIn("macos-probe.sql", verifier)
        self.assertNotIn("make USE_PGXS", verifier)
        self.assertNotIn("curl ", verifier)

    def test_emit_and_import_bind_pg17_core_and_restore_pg18_default(self):
        original = (emitter.PROFILE_ID, emitter.PG_VERSION, emitter.ARCHITECTURE,
                    emitter.PLATFORM, emitter.CORE_SHA256)
        paths = self.fixture.emit()
        retained = self.fixture.import_run()
        receipt = json.loads((self.fixture.output / "publication/current-receipt.json").read_text())
        record = json.loads(paths[-1].read_text())
        self.assertEqual(record["postgresql_version"], "17.11")
        self.assertEqual(record["assembled_core"]["archive"], "postgresql-17.11-macos-arm64.tar.gz")
        self.assertEqual(record["assembled_core"]["sha256"], self.fixture.core_digest)
        self.assertEqual(receipt["profile_id"], "hypopg-publication-macos-arm64-17.11")
        self.assertTrue(any(path.startswith("support/verification/") for path in retained))
        self.assertEqual((emitter.PROFILE_ID, emitter.PG_VERSION, emitter.ARCHITECTURE,
                          emitter.PLATFORM, emitter.CORE_SHA256), original)

    def test_target_config_rejects_core_basename_mismatch(self):
        config = self.fixture.root / "tools/hypopg_macos_pins/17.11-arm64.json"
        value = json.loads(config.read_text())
        value["core_archive"]["basename"] = "postgresql-18.6-macos-arm64.tar.gz"
        config.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            load_target_config(config)


if __name__ == "__main__":
    unittest.main()
