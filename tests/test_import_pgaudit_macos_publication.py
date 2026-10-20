import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import import_pgaudit_macos_publication as importer
import pgaudit_macos_targets


class ImportPgauditMacosPublicationTests(unittest.TestCase):
    def test_incomplete_attempt_is_retained_without_verification_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            root = directory / "repo"
            (root / "support").mkdir(parents=True)
            shutil.copy(Path(__file__).resolve().parents[1] / "support.json", root / "support.json")
            selected = pgaudit_macos_targets._selected("18.6", "arm64")
            selected["core_archive"].update({"run_id": "123456", "sha256": "c" * 64,
                                            "build_id": "github-123456-1", "source_revision": "d" * 40})
            target_config = directory / "target.json"
            target_config.write_text(json.dumps(selected))
            profile_id = selected["profile_id"]
            (root / "support/verification-profiles.json").write_text(json.dumps({
                "schema_version": 1,
                "profiles": {profile_id: {
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
                "profile_id": profile_id,
                "postgresql_version": "18.6",
                "pgaudit_version": "18.0",
                "architecture": "arm64",
                "steps": {"archive-suite": "failure", "symbols": "skipped", "diagnostics": "skipped"},
                "archives_present": {},
            }))
            retained = importer.import_run(root, core, artifact, "123456", target_config=target_config)
            self.assertEqual(len(retained), 1)
            evidence = root / retained[0]
            self.assertEqual(evidence.name, "attempt.json")
            self.assertFalse((root / "support/verification").exists())


if __name__ == "__main__":
    unittest.main()
