import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.metadata_repack import batch


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, name, metadata):
        path = self.root / name
        with tarfile.open(path, "w:gz") as tar:
            for member_name, contents, mode in (
                ("metadata.json", json.dumps(metadata).encode(), 0o640),
                ("payload.bin", b"binary", 0o755),
            ):
                info = tarfile.TarInfo(member_name)
                info.size, info.mode = len(contents), mode
                tar.addfile(info, io.BytesIO(contents))
        return path

    def test_selects_only_allowlisted_archives_with_the_known_missing_fields(self):
        affected = "hypopg-1.4.3-postgresql-18.6-windows-x86_64.tar.gz"
        valid = "hypopg-1.4.3-postgresql-18.6-linux-x86_64.tar.gz"
        self.archive(affected, {"project": "hypopg"})
        self.archive(valid, {"project": "hypopg", "configuration_prerequisites": [],
                             "runtime_prerequisites": []})
        selected = batch._select_defects([{"filename": affected}, {"filename": valid}], self.root)
        self.assertEqual([item[1].name for item in selected], [affected])

    def test_proof_lists_only_unchanged_non_metadata_members(self):
        filename = "pgvector-0.8.7-postgresql-17.11-linux-x86_64.tar.gz"
        source = self.archive(filename, {"project": "pgvector"})
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        proof = batch._proof_document(source, filename, digest, "a" * 64,
                                      {"postgresql_version": {"before": "<missing>", "after": "17.11"}})
        self.assertEqual([m["path"] for m in proof["unchanged_non_metadata_members"]], ["payload.bin"])
        self.assertEqual(proof["unchanged_non_metadata_members"][0]["content_sha256"],
                         hashlib.sha256(b"binary").hexdigest())

    def test_transfer_updates_only_archive_sha_and_noncode_provenance(self):
        original = {"sha256": "b" * 64, "profile_id": "trial", "nested": {"case": "same"}}
        with patch.object(batch.coverage, "validate_verification_record", return_value=True) as validate:
            derived = batch._derive_record(original, "b" * 64, "c" * 64,
                                           {"postgresql_version": "17.11"}, "support/evidence/proof.json",
                                           {}, self.root)
        self.assertEqual(derived["sha256"], "c" * 64)
        self.assertEqual(derived["nested"], original["nested"])
        self.assertEqual(derived["noncode_patch"], {
            "kind": "metadata-only", "original_sha256": "b" * 64,
            "patched_sha256": "c" * 64, "metadata_delta": {"postgresql_version": "17.11"},
            "original_record_sha256": hashlib.sha256(
                json.dumps(original, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(), "proof": "support/evidence/proof.json",
        })
        self.assertEqual(validate.call_count, 2)
        self.assertNotIn("noncode_patch", original)


if __name__ == "__main__":
    unittest.main()
