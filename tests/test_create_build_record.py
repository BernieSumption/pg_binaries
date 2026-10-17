import hashlib
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import create_build_record as tool


class CreateBuildRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.provenance = {
            "build_id": "github-123-1",
            "source_revision": "a" * 40,
            "build_configuration": "postgresql-18;pgvector-0.8.7",
            "platform": "linux",
            "architecture": "x86_64",
        }
        self.core = self.archive("postgresql.tar.gz", "postgresql/manifest.json",
                                {"component": "postgresql", **self.provenance})
        self.vector = self.archive("pgvector.tar.gz", "metadata.json",
                                   {"project": "pgvector", **self.provenance})

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, filename, member, metadata):
        path = self.root / filename
        with tarfile.open(path, "w:gz") as tf:
            data = json.dumps(metadata).encode()
            import io
            info = tarfile.TarInfo(member)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        return path

    def test_record_contains_shared_provenance_and_exact_package_hashes(self):
        symbols = self.root / "index.json"
        symbols.write_text(json.dumps({"files": [
            {"archive": self.core.name,
             "archive_sha256": hashlib.sha256(self.core.read_bytes()).hexdigest()},
            {"archive": self.vector.name,
             "archive_sha256": hashlib.sha256(self.vector.read_bytes()).hexdigest()},
        ]}), encoding="utf-8")
        result = tool.create_record(self.core, self.vector, symbols)
        self.assertEqual(result["record_id"], "github-123-1-linux-x86_64")
        for field, value in self.provenance.items():
            self.assertEqual(result[field], value)
        self.assertEqual(result["packages"]["postgresql"], {
            "archive": self.core.name,
            "sha256": hashlib.sha256(self.core.read_bytes()).hexdigest(),
        })
        self.assertEqual(result["packages"]["pgvector"]["sha256"],
                         hashlib.sha256(self.vector.read_bytes()).hexdigest())
        self.assertEqual(result["symbol_index"], {
            "path": symbols.name,
            "sha256": hashlib.sha256(symbols.read_bytes()).hexdigest(),
        })

    def test_symbol_index_is_optional(self):
        self.assertNotIn("symbol_index", tool.create_record(self.core, self.vector))

    def test_mismatched_provenance_is_rejected(self):
        different = dict(self.provenance, build_id="other-build")
        vector = self.archive("other-vector.tar.gz", "metadata.json", different)
        with self.assertRaisesRegex(ValueError, "build_id values differ"):
            tool.create_record(self.core, vector)

    def test_mismatched_symbol_archive_is_rejected(self):
        symbols = self.root / "index.json"
        symbols.write_text(json.dumps({"files": [
            {"archive": self.core.name, "archive_sha256": "0" * 64},
            {"archive": self.vector.name,
             "archive_sha256": hashlib.sha256(self.vector.read_bytes()).hexdigest()},
        ]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "symbol index archive checksum differs"):
            tool.create_record(self.core, self.vector, symbols)

    def test_optional_builder_image_must_agree(self):
        core = self.archive("core-with-image.tar.gz", "postgresql/manifest.json",
                            dict(self.provenance, builder_image_id="sha256:" + "a" * 64))
        vector = self.archive("vector-with-image.tar.gz", "metadata.json",
                              dict(self.provenance, builder_image_id="sha256:" + "a" * 64))
        result = tool.create_record(core, vector)
        self.assertEqual(result["builder_image_id"], "sha256:" + "a" * 64)


if __name__ == "__main__":
    unittest.main()
