from pathlib import Path
import os
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/collection/version-selection.sh"


class CollectionLinuxVersionSelectionTests(unittest.TestCase):
    def _select(self, version=None):
        command = 'source "$1"; select_collection_versions || exit $?; printf "%s\\n" "${SELECTED_COLLECTION_VERSIONS[@]}"'
        env = os.environ.copy()
        if version is None:
            env.pop("COLLECTION_VERSION", None)
        else:
            env["COLLECTION_VERSION"] = version
        return subprocess.run(["bash", "-c", command, "bash", str(HELPER)],
                              env=env, capture_output=True, text=True)

    def test_unset_version_preserves_both_release_behavior(self):
        result = self._select()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["1.1.1", "2.1.3"])

    def test_selected_version_limits_to_that_release(self):
        for version in ("1.1.1", "2.1.3"):
            with self.subTest(version=version):
                result = self._select(version)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), [version])

    def test_unknown_version_is_rejected(self):
        result = self._select("9.9.9")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsupported Collection version", result.stderr)


if __name__ == "__main__":
    unittest.main()
