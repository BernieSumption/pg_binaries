import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "collection_macos_evidence", REPO / "scripts/collection/check_macos_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class CollectionMacosEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.version = "1.1.1"
        self.archive = self.root / "collection-1.1.1-postgresql-18.6-macos-arm64.tar.gz"
        metadata = {
            "project": "collection", "version": self.version, "sql_names": ["collection"],
            "requires": [], "configuration_prerequisites": [], "runtime_prerequisites": [],
            "postgresql_version": "18.6", "platform": "macos", "architecture": "arm64",
            "source": {
                "url": "https://github.com/aws/pgcollection/archive/refs/tags/v1.1.1.tar.gz",
                "sha256": evidence.VERSIONS[self.version],
            },
            "core_archive": {"basename": evidence.CORE_NAME, "sha256": evidence.CORE_SHA256},
        }
        with tarfile.open(self.archive, "w:gz") as tar:
            self._add(tar, "metadata.json", json.dumps(metadata).encode())
            for name in (
                "collection/lib/collection.dylib",
                "collection/share/extension/collection.control",
                "collection/LICENSES/pgcollection.txt",
                "collection/LICENSES/pgcollection-NOTICE.txt",
                "collection/LICENSES/uthash.txt",
                "collection/LICENSES/collection-inventory.json",
            ):
                self._add(tar, name, b"fixture\n")
        self.core = self.root / evidence.CORE_NAME
        self.core.write_bytes(b"core")
        self.report_path = self.root / "static-analysis.json"
        self.report_path.write_text(json.dumps({
            "passed": True, "architecture": "arm64",
            "inspected_files": [{"file": "lib/collection.dylib"}],
            "archives": [
                {"basename": self.core.name, "sha256": evidence.sha256(self.core)},
                {"basename": self.archive.name, "sha256": evidence.sha256(self.archive)},
            ],
        }))

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _add(tar, name, data):
        import io
        info = tarfile.TarInfo(name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))

    def test_accepts_archive_with_pinned_identity_and_native_payload(self):
        evidence.verify_collection_archive(self.archive, self.version)

    def test_rejects_archive_with_wrong_source_pin(self):
        altered = self.root / "altered.tar.gz"
        with tarfile.open(self.archive, "r:gz") as source, tarfile.open(altered, "w:gz") as output:
            for member in source.getmembers():
                data = source.extractfile(member).read() if member.isfile() else b""
                if member.name == "metadata.json":
                    value = json.loads(data)
                    value["source"]["sha256"] = "0" * 64
                    data = json.dumps(value).encode()
                self._add(output, member.name, data) if member.isfile() else output.addfile(member)
        with self.assertRaisesRegex(evidence.EvidenceError, "metadata identity mismatch"):
            evidence.verify_collection_archive(altered, self.version)

    def test_rejects_report_that_does_not_bind_final_extension_bytes(self):
        report = json.loads(self.report_path.read_text())
        report["archives"][1]["sha256"] = "0" * 64
        self.report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(evidence.EvidenceError, "final archives"):
            evidence.verify_report(self.report_path, [self.core, self.archive])

    def test_checks_archive_checksum_sidecar_against_archive_bytes(self):
        digest = evidence.sha256(self.archive)
        self.archive.with_name(self.archive.name + ".sha256").write_text(
            f"{digest}  {self.archive.name}\n")
        evidence.verify_sidecar(self.archive, digest)
        self.archive.with_name(self.archive.name + ".sha256").write_text(
            f"{'0' * 64}  {self.archive.name}\n")
        with self.assertRaisesRegex(evidence.EvidenceError, "checksum sidecar"):
            evidence.verify_sidecar(self.archive, digest)


if __name__ == "__main__":
    unittest.main()
