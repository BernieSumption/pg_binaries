"""Focused tests for final-byte pg_ivm macOS publication evidence."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import emit_pgivm_macos_x86_64_publication as emitter


class pg_ivmMacOSFixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.core = self.base / "core"
        self.output = self.base / "output"
        for directory in (self.root, self.core, self.output):
            directory.mkdir()
        registry = json.loads(Path("support/verification-profiles.json").read_text())
        profile = registry["profiles"][emitter.PROFILE_ID]
        for relative in profile["sources"]:
            source = Path(relative)
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        shutil.copyfile("support.json", self.root / "support.json")
        shutil.copyfile("support/postgresql-releases.json", self.root / "support/postgresql-releases.json")
        shutil.copyfile("support/verification-profiles.json", self.root / "support/verification-profiles.json")
        self.core_name = f"postgresql-{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz"
        self.extension_name = (f"pg_ivm-{emitter.PGIVM_VERSION}-postgresql-"
                               f"{emitter.PG_VERSION}-{emitter.PLATFORM}.tar.gz")
        self.core_archive = self.core / self.core_name
        self.core_archive.write_bytes(b"fixture core bytes")
        self.core_digest = self.digest(self.core_archive)
        self.core_patch = patch.object(emitter, "CORE_SHA256", self.core_digest)
        self.core_patch.start()
        self.extension = self.output / self.extension_name
        self._archive_extension()
        self.environ = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "12345678901",
                        "GITHUB_REPOSITORY": "BernieSumption/pg_binaries",
                        "GITHUB_SERVER_URL": "https://github.com"}

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _sidecar(self, path):
        path.with_name(path.name + ".sha256").write_text(f"{self.digest(path)}  {path.name}\n")

    def _archive_extension(self):
        metadata = {
            "project": "pg_ivm", "version": emitter.PGIVM_VERSION,
            "sql_names": ["pg_ivm"], "postgresql_version": emitter.PG_VERSION,
            "platform": "macos", "architecture": "x86_64",
            "source": {"url": emitter.SOURCE_URL, "sha256": emitter.SOURCE_SHA256},
            "core_archive": {"basename": self.core_name, "sha256": self.core_digest},
        }
        inventory = {"schema_version": 1, "components": [{
            "component": "pg_ivm", "version": emitter.PGIVM_VERSION,
            "payload_paths": ["lib/pg_ivm.dylib"], "license_file": "pg_ivm.txt",
            "redistribution_review": {
                "status": "resolved", "basis": "Fixture licence review.",
                "source_obligation": "none",
            },
        }]}
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "pg_ivm"
            (package / "lib").mkdir(parents=True)
            (package / "LICENSES").mkdir()
            (package / "lib/pg_ivm.dylib").write_bytes(b"Mach-O fixture")
            (package / "LICENSES/pg_ivm.txt").write_text("PostgreSQL License\n")
            (package / "LICENSES/pg_ivm-inventory.json").write_text(json.dumps(inventory))
            metadata_path = Path(temporary) / "metadata.json"
            metadata_path.write_text(json.dumps(metadata))
            with tarfile.open(self.extension, "w:gz") as archive:
                archive.add(package, arcname="pg_ivm")
                archive.add(metadata_path, arcname="metadata.json")
        self._sidecar(self.core_archive)
        self._sidecar(self.extension)
        digests = {self.core_name: self.core_digest, self.extension_name: self.digest(self.extension)}
        (self.output / "static-analysis.json").write_text(json.dumps({
            "passed": True, "architecture": "x86_64", "inspected_files": ["pg_ivm/lib/pg_ivm.dylib"],
            "archives": digests,
        }))
        (self.output / "probe-output.txt").write_text(
            " postgres_version \n------------------\n 18.6\n(1 row)\n"
            "CREATE EXTENSION\nCREATE TABLE\nINSERT 0 2\n"
            " create_immv \n-------------\n           1\n(1 row)\n"
            "DO\nINSERT 0 1\nDO\nUPDATE 1\nDO\n")

    def emit(self, cases=None):
        return emitter.emit(
            self.root, self.core, self.output, self.output,
            cases or {"archive-suite": "success", "static-analysis": "success"},
            "15.7.9", "macos15/20261017.1", self.environ,
        )

    def close(self):
        self.core_patch.stop()
        self.temp.cleanup()


class pg_ivmMacOSX8664PublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = pg_ivmMacOSFixture()
        self.addCleanup(self.fixture.close)

    def test_emits_archive_bound_receipt_and_record(self):
        paths = self.fixture.emit()
        receipt = json.loads((self.fixture.output / "publication/current-receipt.json").read_text())
        record = json.loads(paths[-1].read_text())
        self.assertEqual(receipt["archives"][self.fixture.core_name], self.fixture.core_digest)
        self.assertEqual(receipt["archives"][self.fixture.extension_name], self.fixture.digest(self.fixture.extension))
        self.assertEqual(record["case_results"], {"archive-suite": "passed", "static-analysis": "passed"})
        self.assertEqual(record["assembled_core"]["sha256"], self.fixture.core_digest)

    def test_incomplete_archives_retain_attempt_only(self):
        self.fixture.extension.unlink()
        paths = self.fixture.emit({"archive-suite": "failure", "static-analysis": "skipped"})
        self.assertEqual([path.name for path in paths], ["attempt.json"])
        self.assertFalse((self.fixture.output / "publication/current-receipt.json").exists())

    def test_rejects_invalid_final_archive_inventory(self):
        self.fixture.extension.unlink()
        package = self.fixture.output / "payload"
        (package / "pg_ivm/LICENSES").mkdir(parents=True)
        (package / "pg_ivm/lib").mkdir()
        (package / "pg_ivm/lib/pg_ivm.dylib").write_bytes(b"native")
        (package / "pg_ivm/LICENSES/pg_ivm.txt").write_text("license\n")
        (package / "pg_ivm/LICENSES/inventory.json").write_text(json.dumps({
            "schema_version": 1, "components": [{
                "component": "pg_ivm", "version": "1.16",
                "payload_paths": ["lib/pg_ivm.dylib"], "license_file": "pg_ivm.txt",
                "redistribution_review": {
                    "status": "resolved", "basis": "Fixture licence review.",
                    "source_obligation": "none",
                },
            }],
        }))
        metadata = {"project": "pg_ivm", "version": emitter.PGIVM_VERSION,
                    "sql_names": ["pg_ivm"], "postgresql_version": emitter.PG_VERSION,
                    "platform": "macos", "architecture": "x86_64",
                    "source": {"url": emitter.SOURCE_URL, "sha256": emitter.SOURCE_SHA256},
                    "core_archive": {"basename": self.fixture.core_name,
                                     "sha256": self.fixture.core_digest}}
        metadata_path = package / "metadata.json"
        metadata_path.write_text(json.dumps(metadata))
        with tarfile.open(self.fixture.extension, "w:gz") as archive:
            archive.add(package / "pg_ivm", arcname="pg_ivm")
            archive.add(metadata_path, arcname="metadata.json")
        self.fixture._sidecar(self.fixture.extension)
        with self.assertRaisesRegex(Exception, "licence inventory"):
            self.fixture.emit()

    def test_rejects_native_payload_without_licence_mapping(self):
        from check_macos_extension_license_inventory import check_archive

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            package = base / "pg_ivm"
            (package / "share/extension").mkdir(parents=True)
            (package / "lib").mkdir()
            (package / "LICENSES").mkdir()
            (package / "share/extension/pg_ivm.control").write_text("default_version = '1.16'\n")
            (package / "lib/pg_ivm.dylib").write_bytes(b"native fixture")
            (package / "LICENSES/pg_ivm.txt").write_text("license\n")
            inventory = {"schema_version": 1, "components": [{
                "component": "pg_ivm", "version": "1.16",
                "payload_paths": ["share/extension"], "license_file": "pg_ivm.txt",
                "redistribution_review": {
                    "status": "resolved", "basis": "Fixture licence review.",
                    "source_obligation": "none",
                },
            }]}
            (package / "LICENSES/pg_ivm-inventory.json").write_text(json.dumps(inventory))
            with tarfile.open(base / "extension.tar.gz", "w:gz") as archive:
                archive.add(package, arcname="pg_ivm")
                metadata = base / "metadata.json"
                metadata.write_text("{}")
                archive.add(metadata, arcname="metadata.json")
            with self.assertRaisesRegex(Exception, "unmapped native payload"):
                check_archive(base / "extension.tar.gz")


if __name__ == "__main__":
    unittest.main()
