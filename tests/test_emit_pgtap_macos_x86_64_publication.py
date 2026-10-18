"""Focused tests for final-byte pgTAP macOS publication evidence."""

import hashlib
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import emit_pgtap_macos_x86_64_publication as emitter

INTEL_CORE_SHA256 = "5ec45e48bad1439860f0143fd6f2cbc04a86cfa456beef8c5ca9040960ea3f40"


class PgTapMacOSX8664PublicationTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(emitter.CORE_SHA256, INTEL_CORE_SHA256)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.core = Path(self.temp.name) / "core"
        self.out = Path(self.temp.name) / "output"
        self.root.mkdir()
        self.core.mkdir()
        self.out.mkdir()
        (self.root / "support").mkdir()
        (self.root / "support.json").write_text(Path("support.json").read_text())
        (self.root / "support/postgresql-releases.json").write_text(
            Path("support/postgresql-releases.json").read_text())
        shutil_registry = Path("support/verification-profiles.json").read_text()
        (self.root / "support/verification-profiles.json").write_text(shutil_registry)
        sources = json.loads(shutil_registry)["profiles"][emitter.PROFILE_ID]["sources"]
        for source in sources:
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                source_path = Path(source)
                if source_path.exists():
                    destination.write_bytes(source_path.read_bytes())
                else:
                    destination.write_text("profile source fixture\n")
        self.core_name = f"postgresql-{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz"
        self.extension_name = f"pgtap-{emitter.PGTAP_VERSION}-postgresql-{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz"
        self.core_archive = self.core / self.core_name
        self.core_archive.write_bytes(b"fixture core archive")
        self.core_digest = hashlib.sha256(self.core_archive.read_bytes()).hexdigest()
        self.core_digest_patch = patch.object(emitter, "CORE_SHA256", self.core_digest)
        self.core_digest_patch.start()
        self.addCleanup(self.core_digest_patch.stop)
        self._sidecar(self.core_archive)
        self.extension = self.out / self.extension_name
        metadata = {
            "project": "pgtap", "version": emitter.PGTAP_VERSION, "sql_names": ["pgtap"],
            "postgresql_version": emitter.PG_VERSION, "platform": "macos", "architecture": "x86_64",
            "source": {"url": emitter.SOURCE_URL, "sha256": emitter.SOURCE_SHA256},
            "core_archive": {"basename": self.core_name, "sha256": self.core_digest},
        }
        metadata_path = Path(self.temp.name) / "metadata.json"
        metadata_path.write_text(json.dumps(metadata))
        with tarfile.open(self.extension, "w:gz") as archive:
            archive.add(metadata_path, arcname="metadata.json")
        self._sidecar(self.extension)
        self.report()
        self.environ = {
            "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "12345678901",
            "GITHUB_REPOSITORY": "BernieSumption/pg_binaries", "GITHUB_SERVER_URL": "https://github.com",
        }

    def _sidecar(self, path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n")

    def report(self):
        digests = {self.core_name: hashlib.sha256(self.core_archive.read_bytes()).hexdigest(),
                   self.extension_name: hashlib.sha256(self.extension.read_bytes()).hexdigest()}
        (self.out / "static-analysis.json").write_text(json.dumps({
            "passed": True, "architecture": "x86_64", "inspected_files": ["bin/postgres"],
            "archives": digests,
        }))
        (self.out / "probe-output.txt").write_text("1..4\nok 1\nok 2\nok 3\nok 4\n")
        (self.out / "build-log.txt").write_text("PASS feasibility probe\n")

    def emit(self, outcomes=None):
        return emitter.emit(
            self.root, self.core, self.out, self.out,
            outcomes or {"archive-suite": "success", "static-analysis": "success"},
            "15.7.9", "macos15/test-image", self.environ,
        )

    def test_emits_receipt_bound_to_both_archive_hashes(self):
        paths = self.emit()
        receipt = json.loads((self.out / "publication/current-receipt.json").read_text())
        record = json.loads(paths[-1].read_text())
        self.assertEqual(receipt["archives"][self.core_name], self.core_digest)
        self.assertEqual(receipt["archives"][self.extension_name], emitter.sha256_file(self.extension))
        self.assertEqual(record["case_results"], {"archive-suite": "passed", "static-analysis": "passed"})
        self.assertEqual(record["assembled_core"]["sha256"], self.core_digest)
        self.assertNotIn("symbols", receipt["case_results"])

    def test_incomplete_archives_retain_raw_attempt_only(self):
        self.extension.unlink()
        result = self.emit()
        attempt = json.loads(result[0].read_text())
        self.assertEqual(attempt["archives_present"][self.extension_name], False)
        self.assertFalse((self.out / "publication/current-receipt.json").exists())
        self.assertFalse(list((self.out / "publication/records").glob("*.json")))

    def test_modified_core_checksum_is_rejected(self):
        self.core_archive.write_bytes(b"changed core bytes")
        with self.assertRaisesRegex(Exception, "checksum sidecar"):
            self.emit()


if __name__ == "__main__":
    unittest.main()
