import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "source_archive", ROOT / "tools" / "source_archive.py")
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


class SourceArchiveTests(unittest.TestCase):
    def test_selected_postgresql_and_pgvector_archives(self):
        self.assertEqual(source.source_archive("postgresql", "18.6", "tar.gz"), {
            "url": "https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.gz",
            "sha256": "983ee554ec53dbeb9b70797bef9fcf4e67e117e7e48ca1463cc80b3ff8e8ff3f",
        })
        self.assertEqual(source.source_archive("pgvector", "0.8.7", "tar.gz"), {
            "url": "https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.7.tar.gz",
            "sha256": "cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85",
        })

    def test_unknown_component_version_and_format_are_rejected(self):
        for args in (("unknown", "1", "tar.gz"), ("postgresql", "99.1", "tar.gz"),
                     ("pgvector", "0.8.7", "tar.bz2")):
            with self.subTest(args=args), self.assertRaises(source.SourceArchiveError):
                source.source_archive(*args)

    def test_missing_and_invalid_digest_are_rejected(self):
        for digest in (None, "not-a-digest", "a" * 63, "A" * 64):
            with self.subTest(digest=digest), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "support").mkdir()
                (root / "support").joinpath("postgresql-releases.json").write_text(
                    json.dumps({"releases": [{"version": "18.6", "source_archives": {
                        "tar.gz": {"url": "https://example.test/source.tar.gz", "sha256": digest}
                    }}]}), encoding="utf-8")
                with self.assertRaisesRegex(source.SourceArchiveError, "SHA-256"):
                    source.source_archive("postgresql", "18.6", "tar.gz", root)


if __name__ == "__main__":
    unittest.main()
