import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "pgvector_archive_input", Path(__file__).resolve().parents[1] / "scripts/pgvector/archive_input.py")
archive_input = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive_input)


class PgvectorCoreInputTests(unittest.TestCase):
    def test_core_source_identity_must_match_selected_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "postgresql-18.6-linux-x86_64.tar.gz"
            source_sha = "a" * 64
            manifest = {"component": "postgresql", "version": "18.6", "platform": "linux",
                        "architecture": "x86_64", "source_archive": {"sha256": source_sha}}
            payload = json.dumps(manifest).encode()
            with tarfile.open(archive, "w:gz") as output:
                member = tarfile.TarInfo("postgresql/manifest.json")
                member.size = len(payload)
                output.addfile(member, io.BytesIO(payload))
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            sidecar = root / (archive.name + ".sha256")
            sidecar.write_text(f"{digest}  {archive.name}\n")

            self.assertEqual(archive_input.validate_core(
                archive, sidecar, digest, "18.6", "x86_64", source_sha), digest)
            with self.assertRaisesRegex(ValueError, "source archive does not match"):
                archive_input.validate_core(
                    archive, sidecar, digest, "18.6", "x86_64", "b" * 64)


if __name__ == "__main__":
    unittest.main()
