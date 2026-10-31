from pathlib import Path
import re
import stat
import tempfile
import unittest
from unittest.mock import patch

from packages.postgresql.probes.environment import _probe_scratch_directory


class ProbeScratchDirectoryTests(unittest.TestCase):
    def test_posix_directory_remains_private(self):
        with tempfile.TemporaryDirectory() as parent:
            path = _probe_scratch_directory(parent, "pg-probe-")
            try:
                self.assertEqual(0o700, stat.S_IMODE(path.stat().st_mode))
            finally:
                path.rmdir()

    def test_windows_directory_uses_default_inherited_permissions(self):
        posix_path = type(Path())
        original_mkdir = posix_path.mkdir
        with tempfile.TemporaryDirectory() as parent, \
                patch("packages.postgresql.probes.environment.os.name", "nt"), \
                patch("packages.postgresql.probes.environment.Path", posix_path), \
                patch.object(posix_path, "mkdir", autospec=True, side_effect=original_mkdir) as mkdir:
            path = _probe_scratch_directory(parent, "pg-probe-")
            try:
                self.assertTrue(path.is_dir())
                self.assertRegex(path.name, re.compile(r"^pg-probe-[0-9a-f]{12}$"))
                mkdir.assert_called_once_with(path)
            finally:
                path.rmdir()


if __name__ == "__main__":
    unittest.main()
