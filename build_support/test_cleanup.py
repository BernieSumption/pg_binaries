import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from build_support.cleanup import remove_tree
from build_support.iteration import MARKER, prepare_reused_workspace, record_dependency_success


@unittest.skipUnless(os.name == "nt", "Windows read-only file attributes")
class WindowsCleanupTests(unittest.TestCase):
    def test_recipe_change_removes_readonly_sources_and_preserves_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            keys = dict(source_key="s", context_key="c", dependency_key="d", main_key="one")
            prepare_reused_workspace(workspace, "demo", "windows-x86_64", keys)
            record_dependency_success(workspace, "d")
            retained = [workspace / "build/dependencies/ready", workspace / "postgresql/private",
                        root / "unrelated/keep"]
            for path in retained:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("retained")
            source = workspace / "sources/patchelf/build-aux/compile"
            source.parent.mkdir(parents=True)
            source.write_text("source")
            source.chmod(stat.S_IREAD)
            self.assertTrue(source.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
            keys["main_key"] = "two"
            prepare_reused_workspace(workspace, "demo", "windows-x86_64", keys)
            self.assertEqual(list((workspace / "sources").iterdir()), [])
            for path in retained:
                self.assertEqual(path.read_text(), "retained")
            self.assertEqual(json.loads((workspace / MARKER).read_text())["dependency_success_key"], "d")

    def test_nonreadonly_permission_error_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "normal"
            source.write_text("source")
            error = PermissionError("file held by another process")

            def fail(path, *, onerror):
                onerror(os.unlink, str(source), (PermissionError, error, None))

            with patch("build_support.cleanup.shutil.rmtree", side_effect=fail):
                with self.assertRaises(PermissionError) as raised:
                    remove_tree(root)
            self.assertIs(raised.exception, error)
            self.assertTrue(source.exists())


class CleanupTests(unittest.TestCase):
    def test_missing_tree_is_only_allowed_when_requested(self):
        with tempfile.TemporaryDirectory() as temporary:
            absent = Path(temporary) / "absent"
            remove_tree(absent, missing_ok=True)
            with self.assertRaises(FileNotFoundError):
                remove_tree(absent)
