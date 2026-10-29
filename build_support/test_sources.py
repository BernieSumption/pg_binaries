import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from build_support.sources import download, extract


class SourceTests(unittest.TestCase):
    def archive(self, root, entries):
        archive = root / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for name, value in entries:
                entry = tarfile.TarInfo(name)
                if isinstance(value, tuple):
                    entry.type = tarfile.SYMTYPE
                    entry.linkname = value[0]
                    tar.addfile(entry)
                else:
                    entry.size = len(value)
                    tar.addfile(entry, io.BytesIO(value))
        return archive

    def test_unwraps_single_directory_and_preserves_subdirectories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.archive(root, [("release/src/file.c", b"source"), ("release/COPYING", b"terms")])
            extract(archive, root / "tree")
            self.assertEqual((root / "tree/src/file.c").read_bytes(), b"source")
            self.assertTrue((root / "tree/COPYING").is_file())

    def test_keeps_multiple_top_level_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extract(self.archive(root, [("src/file.c", b"source"), ("COPYING", b"terms")]), root / "tree")
            self.assertTrue((root / "tree/src/file.c").is_file())

    def test_rejects_paths_and_links_escaping_tree(self):
        for entries in [[("../outside", b"bad")], [("release/link", ("../../outside",))],
                        [("release/file", b"ok"), ("release/link", ("../outside",))]]:
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with self.assertRaises(ValueError):
                    extract(self.archive(root, entries), root / "tree")
                self.assertFalse((root / "tree").exists())
                self.assertFalse((root / "outside").exists())

    def test_checksum_failure_never_enters_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = {"url": "https://example.com/source.tar.gz", "sha256": "0" * 64}
            def fetch(command, **kwargs):
                Path(command[-1]).write_bytes(b"wrong content")
            with patch("build_support.sources.subprocess.run", side_effect=fetch), self.assertRaisesRegex(ValueError, "checksum mismatch"):
                download(source, root)
            self.assertEqual(list(root.iterdir()), [])

    def test_cache_is_verified_before_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            digest = hashlib.sha256(b"source").hexdigest()
            (root / digest).write_bytes(b"source")
            with patch("build_support.sources.subprocess.run") as fetch:
                self.assertEqual(download({"url": "https://example.com/source", "sha256": digest}, root), root / digest)
                fetch.assert_not_called()
