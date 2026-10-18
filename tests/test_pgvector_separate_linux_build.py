import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "archive_input", ROOT / "scripts/pgvector/archive_input.py"
)
archive_input = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive_input)

def write_tar(path, members):
    with tarfile.open(path, "w:gz") as archive:
        for name, content in members.items():
            data = content if isinstance(content, bytes) else content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))

class SeparateLinuxPgvectorBuildInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.core = self.directory / "postgresql-18.6-linux-x86_64.tar.gz"
        self.manifest = {
            "component": "postgresql", "version": "18.6",
            "platform": "linux", "architecture": "x86_64",
            "source_archive": {"sha256": "a" * 64},
        }
        self.write_core()
        self.sidecar = self.directory / (self.core.name + ".sha256")
        self.refresh_sidecar()

    def tearDown(self):
        self.temp.cleanup()

    def write_core(self):
        write_tar(self.core, {
            "postgresql/manifest.json": json.dumps(self.manifest),
            "postgresql/bin/pg_config": "fixture",
        })

    def refresh_sidecar(self):
        self.sidecar.write_text(
            f"{archive_input.sha256(self.core)}  {self.core.name}\n",
            encoding="utf-8",
        )

    def test_accepts_exact_pinned_core_identity_and_checksum(self):
        expected = archive_input.sha256(self.core)
        digest = archive_input.validate_core(self.core, self.sidecar, expected, "18.6", "x86_64", "a" * 64)
        self.assertEqual(digest, archive_input.sha256(self.core))

    def test_rejects_core_bytes_that_do_not_match_sidecar(self):
        self.core.write_bytes(self.core.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "checksum"):
            archive_input.validate_core(self.core, self.sidecar, archive_input.sha256(self.core), "18.6", "x86_64", "a" * 64)

    def test_rejects_wrong_core_manifest_architecture(self):
        self.manifest["architecture"] = "arm64"
        self.write_core()
        self.refresh_sidecar()
        with self.assertRaisesRegex(ValueError, "manifest identity"):
            archive_input.validate_core(self.core, self.sidecar, archive_input.sha256(self.core), "18.6", "x86_64", "a" * 64)

    def test_rejects_wrong_core_release_or_filename(self):
        with self.assertRaisesRegex(ValueError, "requires"):
            archive_input.validate_core(self.core, self.sidecar, archive_input.sha256(self.core), "17.11", "x86_64", "a" * 64)
        arm_name = self.directory / "postgresql-18.6-linux-arm64.tar.gz"
        arm_name.write_bytes(self.core.read_bytes())
        with self.assertRaisesRegex(ValueError, "requires"):
            archive_input.validate_core(arm_name, self.sidecar, archive_input.sha256(arm_name), "18.6", "arm64", "a" * 64)

    def test_rejects_replaced_archive_even_when_sidecar_is_replaced_too(self):
        self.manifest["build_id"] = "replacement"
        self.write_core()
        self.refresh_sidecar()
        trusted_sha = "a" * 64
        with self.assertRaisesRegex(ValueError, "separately supplied"):
            archive_input.validate_core(self.core, self.sidecar, trusted_sha, "18.6", "x86_64", "a" * 64)

    def test_accepts_selected_postgresql_17_core_and_source_identity(self):
        self.core = self.directory / "postgresql-17.11-linux-x86_64.tar.gz"
        self.manifest["version"] = "17.11"
        self.write_core()
        self.sidecar = self.directory / (self.core.name + ".sha256")
        self.refresh_sidecar()
        self.assertEqual(archive_input.validate_core(
            self.core, self.sidecar, archive_input.sha256(self.core), "17.11", "x86_64", "a" * 64),
            archive_input.sha256(self.core))

    def test_source_must_match_pin_and_have_expected_root(self):
        source = self.directory / "source.tar.gz"
        write_tar(source, {"pgvector-0.8.7/Makefile": "all:"})
        digest = archive_input.sha256(source)
        archive_input.validate_source(source, digest)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            archive_input.validate_source(source, "0" * 64)
        wrong = self.directory / "wrong.tar.gz"
        write_tar(wrong, {"pgvector-0.8.6/Makefile": "all:"})
        with self.assertRaisesRegex(ValueError, "root"):
            archive_input.validate_source(wrong, archive_input.sha256(wrong))

if __name__ == "__main__":
    unittest.main()
