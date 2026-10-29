import hashlib
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from build_support.bundling import finish_extension


class FinishExtensionTests(unittest.TestCase):
    def test_archive_has_runtime_layout_licence_permissions_and_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            payload = workspace / "payload"
            (payload / "lib").mkdir(parents=True)
            module = payload / "lib/example.so"
            module.write_bytes(b"compiled module")
            module.chmod(0o755)
            with patch("build_support.bundling.subprocess.run") as run:
                archive = finish_extension(workspace, "linux-arm64", root / "output", "example", "18.6")
            self.assertEqual(run.call_count, 2)
            with tarfile.open(archive) as tar:
                self.assertEqual(tar.getmember("postgresql/lib/example.so").mode, 0o644)
                self.assertEqual(tar.getmember("postgresql/lib").mode, 0o755)
                self.assertIn(b"LICENSES.md", tar.extractfile("postgresql/LICENCE").read())
                self.assertEqual(tar.extractfile("postgresql/lib/example.so").read(), b"compiled module")
            checksum = Path(str(archive) + ".sha256").read_text().split()[0]
            self.assertEqual(checksum, hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertTrue(module.exists())

    def test_failed_bundling_does_not_replace_previous_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "workspace/payload").mkdir(parents=True)
            output = root / "output"
            output.mkdir()
            archive = output / "example-postgresql-18.6-macos-arm64.tar.gz"
            archive.write_bytes(b"previous successful archive")
            with patch("build_support.bundling.subprocess.run", side_effect=RuntimeError("missing dependency")):
                with self.assertRaisesRegex(RuntimeError, "missing dependency"):
                    finish_extension(root / "workspace", "macos-arm64", output, "example", "18.6")
            self.assertEqual(archive.read_bytes(), b"previous successful archive")
