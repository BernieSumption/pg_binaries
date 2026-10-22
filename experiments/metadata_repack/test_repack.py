import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.metadata_repack.repack import RepackError, repack, verify_repack


class MetadataRepackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, filename, metadata):
        path = self.root / filename
        with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
            for name, payload, mode in (
                ("metadata.json", json.dumps(metadata).encode(), 0o640),
                ("extension/lib/module.so", b"binary payload", 0o755),
            ):
                info = tarfile.TarInfo(name)
                info.mode, info.size, info.mtime = mode, len(payload), 1700000000
                tar.addfile(info, io.BytesIO(payload))
            link = tarfile.TarInfo("extension/lib/module-link.so")
            link.type, link.mode, link.linkname = tarfile.SYMTYPE, 0o777, "module.so"
            tar.addfile(link)
        return path

    def test_adds_pgvector_version_and_preserves_other_members(self):
        source = self.archive("pgvector-0.8.7-postgresql-17.11-linux-x86_64.tar.gz", {"project": "pgvector"})
        output = self.root / "patched.tar.gz"
        result = repack(source, "postgresql-17.11-linux-x86_64.tar.gz", output)
        self.assertEqual(result["added"], {"postgresql_version": "17.11"})
        self.assertTrue(verify_repack(source, output, {"postgresql_version": "17.11"}))
        with tarfile.open(output) as tar:
            metadata = json.load(tar.extractfile("metadata.json"))
            self.assertEqual(metadata["postgresql_version"], "17.11")
            self.assertEqual(tar.getmember("metadata.json").mode, 0o640)

    def test_adds_only_empty_prerequisite_arrays_for_allowlisted_targets(self):
        cases = (
            ("hypopg-1.4.3-postgresql-18.6-windows-x86_64.tar.gz", "hypopg"),
            ("pg_jsonschema-0.3.4-postgresql-18.6-windows-x86_64.tar.gz", "pg_jsonschema"),
            ("pg_jsonschema-0.3.4-postgresql-18.6-macos-arm64.tar.gz", "pg_jsonschema"),
        )
        for filename, project in cases:
            with self.subTest(filename=filename):
                source = self.archive(filename, {"project": project})
                platform = "windows" if "windows" in filename else "macos"
                output = self.root / (project + "-" + platform + "-patched.tar.gz")
                result = repack(source, "postgresql-18.6-" + ("windows-x86_64" if "windows" in filename else "macos-arm64") + ".tar.gz", output)
                self.assertEqual(result["added"], {"configuration_prerequisites": [], "runtime_prerequisites": []})

    def test_rejects_target_mismatch_existing_conflicts_and_unlisted_archive(self):
        cases = (
            ("pgvector-0.8.7-postgresql-17.11-linux-x86_64.tar.gz", {"project": "pgvector"}, "postgresql-18.6-linux-x86_64.tar.gz"),
            ("pgvector-0.8.7-postgresql-17.11-linux-x86_64.tar.gz", {"project": "pgvector", "postgresql_version": "16.15"}, "postgresql-17.11-linux-x86_64.tar.gz"),
            ("hypopg-1.4.3-postgresql-18.6-windows-x86_64.tar.gz", {"project": "hypopg", "runtime_prerequisites": ["conflict"]}, "postgresql-18.6-windows-x86_64.tar.gz"),
            ("hypopg-1.4.3-postgresql-18.6-linux-x86_64.tar.gz", {"project": "hypopg"}, "postgresql-18.6-linux-x86_64.tar.gz"),
        )
        for filename, metadata, core in cases:
            with self.subTest(filename=filename, metadata=metadata):
                source = self.archive(filename, metadata)
                with self.assertRaises(RepackError):
                    repack(source, core, self.root / "rejected.tar.gz")


if __name__ == "__main__":
    unittest.main()
