import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import import_pgaudit_macos_publication as importer


class ImportPgauditMacosPublicationTests(unittest.TestCase):
    def test_incomplete_attempt_is_retained_without_verification_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            root = directory / "repo"
            (root / "support").mkdir(parents=True)
            shutil.copy(Path(__file__).resolve().parents[1] / "support.json", root / "support.json")
            (root / "support/verification-profiles.json").write_text(json.dumps({
                "schema_version": 1,
                "profiles": {importer.PROFILE_ID: {
                    "scope": "publication", "platforms": ["macos-arm64"],
                    "case_ids": ["archive-suite", "diagnostics", "symbols"],
                    "sources": ["profile-source.txt"],
                }},
            }))
            (root / "profile-source.txt").write_text("profile source\n")
            core, artifact = directory / "core", directory / "artifact"
            (artifact / "publication").mkdir(parents=True)
            (artifact / "publication/attempt.json").write_text(json.dumps({
                "schema_version": 1,
                "run_id": "123456",
                "source_revision": "a" * 40,
                "profile_id": importer.PROFILE_ID,
                "postgresql_version": "18.6",
                "pgaudit_version": "18.0",
                "architecture": "arm64",
                "steps": {"archive-suite": "failure", "symbols": "skipped", "diagnostics": "skipped"},
                "archives_present": {},
            }))
            retained = importer.import_run(root, core, artifact, "123456")
            self.assertEqual(len(retained), 1)
            evidence = root / retained[0]
            self.assertEqual(evidence.name, "attempt.json")
            self.assertFalse((root / "support/verification").exists())


if __name__ == "__main__":
    unittest.main()
