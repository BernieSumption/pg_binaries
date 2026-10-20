import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MacOSCoreResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "scripts/macos/resolve-core.sh").read_text(encoding="utf-8")
        match = re.search(
            r'python3 - "\$builder_json".*?<<\'PY\'\n(.*?)\nPY', source, re.DOTALL
        )
        if match is None:
            raise AssertionError("macOS core builder provenance check was not found")
        cls.check = match.group(1)

    def run_check(self, path):
        run = {
            "id": 39431576443,
            "run_attempt": 1,
            "repository": {"full_name": "owner/repo"},
            "head_repository": {"full_name": "owner/repo"},
            "head_branch": "spike",
            "event": "workflow_dispatch",
            "status": "completed",
            "conclusion": "success",
            "path": path,
            "head_sha": "a" * 40,
        }
        return subprocess.run(
            [sys.executable, "-c", self.check, json.dumps(run), "owner/repo", "spike",
             "39431576443", "1", "a" * 40, "x86_64",
             "postgresql-macos-selected-publication.yml"],
            text=True, capture_output=True,
        )

    def test_accepts_workflow_run_path_with_ref_suffix(self):
        result = self.run_check(
            ".github/workflows/postgresql-macos-selected-publication.yml@refs/heads/spike"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_different_workflow_even_with_ref_suffix(self):
        result = self.run_check(
            ".github/workflows/other.yml@refs/heads/spike"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pinned macOS core builder run does not match its archive", result.stderr)


if __name__ == "__main__":
    unittest.main()
