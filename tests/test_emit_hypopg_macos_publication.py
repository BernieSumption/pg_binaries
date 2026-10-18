"""Focused tests for final-byte HypoPG macOS publication evidence."""

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import emit_hypopg_macos_publication as emitter
from hypopg_macos_target import load_target_config


class HypoPGMacOSFixture:
    def __init__(self, target=None):
        self.target = target or emitter._default_target()
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.core = self.base / "core"
        self.output = self.base / "output"
        for directory in (self.root, self.core, self.output):
            directory.mkdir()
        registry = json.loads(Path("support/verification-profiles.json").read_text())
        profile = registry["profiles"][self.target.profile_id]
        for relative in profile["sources"]:
            source = Path(relative)
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        shutil.copyfile("support.json", self.root / "support.json")
        shutil.copyfile("support/postgresql-releases.json", self.root / "support/postgresql-releases.json")
        shutil.copyfile("support/verification-profiles.json", self.root / "support/verification-profiles.json")
        self.core_name = self.target.core_basename
        self.extension_name = self.target.extension_basename
        self.core_archive = self.core / self.core_name
        self.core_archive.write_bytes(b"fixture core bytes")
        self.core_digest = self.digest(self.core_archive)
        self.target = replace(self.target, core_sha256=self.core_digest)
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
            "project": "hypopg", "version": emitter.HYPOPG_VERSION,
            "sql_names": ["hypopg"], "postgresql_version": self.target.postgresql_version,
            "platform": "macos", "architecture": self.target.architecture,
            "source": {"url": emitter.SOURCE_URL, "sha256": emitter.SOURCE_SHA256},
            "core_archive": {"basename": self.core_name, "sha256": self.core_digest},
        }
        inventory = {"schema_version": 1, "components": [{
            "component": "hypopg", "version": emitter.HYPOPG_VERSION,
            "payload_paths": ["lib/hypopg.dylib"], "license_file": "HypoPG.txt",
            "redistribution_review": {
                "status": "resolved", "basis": "Fixture licence review.",
                "source_obligation": "none",
            },
        }]}
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "hypopg"
            (package / "lib").mkdir(parents=True)
            (package / "LICENSES").mkdir()
            (package / "lib/hypopg.dylib").write_bytes(b"Mach-O fixture")
            (package / "LICENSES/HypoPG.txt").write_text("PostgreSQL License\n")
            (package / "LICENSES/hypopg-inventory.json").write_text(json.dumps(inventory))
            metadata_path = Path(temporary) / "metadata.json"
            metadata_path.write_text(json.dumps(metadata))
            with tarfile.open(self.extension, "w:gz") as archive:
                archive.add(package, arcname="hypopg")
                archive.add(metadata_path, arcname="metadata.json")
        self._sidecar(self.core_archive)
        self._sidecar(self.extension)
        digests = {self.core_name: self.core_digest, self.extension_name: self.digest(self.extension)}
        (self.output / "static-analysis.json").write_text(json.dumps({
            "passed": True, "architecture": "arm64", "inspected_files": ["hypopg/lib/hypopg.dylib"],
            "archives": digests,
        }))
        (self.output / "probe-output.txt").write_text(
            f"{self.target.postgresql_version.split('.')[0]}\npostgres_major_matches\nt\n"
            "hypothetical_index_created\nt\nIndex Scan using btree_hypo_probe_id\n0\n")

    def emit(self, cases=None):
        return emitter.emit(
            self.root, self.core, self.output, self.output,
            cases or {"archive-suite": "success", "static-analysis": "success"},
            "15.7.9", "macos15/20261017.1", self.environ, target=self.target,
        )

    def import_run(self, run_id="12345678901"):
        import import_hypopg_macos_publication as importer
        return importer.import_run(self.root, self.core, self.output, run_id, self.target)

    def close(self):
        self.temp.cleanup()


class HypoPGMacOSPublicationTests(unittest.TestCase):
    def test_arm64_pins_match_current_core_record(self):
        root = Path(__file__).resolve().parents[1]
        core = json.loads((root / "support/verification/postgresql-18.6-macos-arm64-current-39093804232.json").read_text())
        run_id = core["ci"]["run_id"]
        source_revision = core["ci"]["source_revision"]
        workflow = (root / ".github/workflows/hypopg-macos-arm64-selected-publication.yml").read_text()
        script = (root / "scripts/hypopg/macos-feasibility.sh").read_text()
        emitter_source = (root / "tools/emit_hypopg_macos_publication.py").read_text()
        pin = json.loads((root / "tools/hypopg_macos_pins/18.6-arm64.json").read_text())
        self.assertIn("scripts/macos/resolve-core.sh", workflow)
        self.assertEqual(pin["core_archive"]["run_id"], run_id)
        self.assertEqual(pin["core_archive"]["build_id"], f"github-{run_id}-1")
        self.assertEqual(pin["core_archive"]["source_revision"], source_revision)
        self.assertEqual(pin["core_archive"]["sha256"], core["sha256"])
        self.assertIn("load_target_config", script)
        self.assertIn(f'CORE_SHA256 = "{core["sha256"]}"', emitter_source)

    def setUp(self):
        self.fixture = HypoPGMacOSFixture()
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
        (package / "hypopg/LICENSES").mkdir(parents=True)
        (package / "hypopg/lib").mkdir()
        (package / "hypopg/lib/hypopg.dylib").write_bytes(b"native")
        (package / "hypopg/LICENSES/HypoPG.txt").write_text("license\n")
        (package / "hypopg/LICENSES/inventory.json").write_text(json.dumps({
            "schema_version": 1, "components": [{
                "component": "hypopg", "version": "1.4.3",
                "payload_paths": ["lib/hypopg.dylib"], "license_file": "HypoPG.txt",
                "redistribution_review": {
                    "status": "resolved", "basis": "Fixture licence review.",
                    "source_obligation": "none",
                },
            }],
        }))
        metadata = {"project": "hypopg", "version": emitter.HYPOPG_VERSION,
                    "sql_names": ["hypopg"], "postgresql_version": emitter.PG_VERSION,
                    "platform": "macos", "architecture": "arm64",
                    "source": {"url": emitter.SOURCE_URL, "sha256": emitter.SOURCE_SHA256},
                    "core_archive": {"basename": self.fixture.core_name,
                                     "sha256": self.fixture.core_digest}}
        metadata_path = package / "metadata.json"
        metadata_path.write_text(json.dumps(metadata))
        with tarfile.open(self.fixture.extension, "w:gz") as archive:
            archive.add(package / "hypopg", arcname="hypopg")
            archive.add(metadata_path, arcname="metadata.json")
        self.fixture._sidecar(self.fixture.extension)
        with self.assertRaisesRegex(Exception, "licence inventory"):
            self.fixture.emit()

    def test_rejects_native_payload_without_licence_mapping(self):
        from check_macos_extension_license_inventory import check_archive

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            package = base / "hypopg"
            (package / "share/extension").mkdir(parents=True)
            (package / "lib").mkdir()
            (package / "LICENSES").mkdir()
            (package / "share/extension/hypopg.control").write_text("default_version = '1.4.3'\n")
            (package / "lib/hypopg.dylib").write_bytes(b"native fixture")
            (package / "LICENSES/HypoPG.txt").write_text("license\n")
            inventory = {"schema_version": 1, "components": [{
                "component": "hypopg", "version": "1.4.3",
                "payload_paths": ["share/extension"], "license_file": "HypoPG.txt",
                "redistribution_review": {
                    "status": "resolved", "basis": "Fixture licence review.",
                    "source_obligation": "none",
                },
            }]}
            (package / "LICENSES/hypopg-inventory.json").write_text(json.dumps(inventory))
            with tarfile.open(base / "extension.tar.gz", "w:gz") as archive:
                archive.add(package, arcname="hypopg")
                metadata = base / "metadata.json"
                metadata.write_text("{}")
                archive.add(metadata, arcname="metadata.json")
            with self.assertRaisesRegex(Exception, "unmapped native payload"):
                check_archive(base / "extension.tar.gz")


if __name__ == "__main__":
    unittest.main()
