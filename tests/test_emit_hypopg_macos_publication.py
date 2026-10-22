"""Focused tests for final-byte HypoPG macOS publication evidence."""

import hashlib
import importlib.util
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
from hypopg_macos_target import (SOURCE_SHA256, SOURCE_URL, HypoPGMacosTarget,
                                 base_target)

_POINTER_SPEC = importlib.util.spec_from_file_location(
    "license_pointer", Path(__file__).resolve().parents[1] / "tools" / "license_pointer.py")
license_pointer = importlib.util.module_from_spec(_POINTER_SPEC)
_POINTER_SPEC.loader.exec_module(license_pointer)


def fixture_target(postgresql_version="18.6", architecture="arm64"):
    base = base_target(postgresql_version, architecture)
    core_name = base["core_archive"]["basename"]
    return HypoPGMacosTarget(
        profile_id=base["profile_id"], postgresql_version=postgresql_version,
        architecture=architecture, platform=base["platform"], core_basename=core_name,
        core_run_id="12345678900", core_sha256="0" * 64,
        core_build_id="github-12345678900-1", core_source_revision="a" * 40,
    )


def fixture_target_config(target):
    return {
        "schema_version": 1,
        "profile_id": target.profile_id,
        "postgresql_version": target.postgresql_version,
        "architecture": target.architecture,
        "platform": target.platform,
        "core_archive": {
            "basename": target.core_basename, "run_id": target.core_run_id,
            "sha256": target.core_sha256, "build_id": target.core_build_id,
            "source_revision": target.core_source_revision,
        },
        "source": {"url": SOURCE_URL, "sha256": SOURCE_SHA256},
    }


class HypoPGMacOSFixture:
    def __init__(self, target=None):
        self.target = target or fixture_target()
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
        (self.root / "support").mkdir(exist_ok=True)
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
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "hypopg"
            (package / "lib").mkdir(parents=True)
            (package / "lib/hypopg.dylib").write_bytes(b"Mach-O fixture")
            license_pointer.write_pointer(package, "hypopg")
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
    def test_arm64_selected_workflow_resolves_the_selected_core(self):
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github/workflows/hypopg-macos-arm64-selected-publication.yml").read_text()
        self.assertIn("scripts/macos/resolve-core.sh", workflow)
        self.assertIn("tools/hypopg_macos_target.py", workflow)
        self.assertIn("--postgresql-version \"$POSTGRESQL_VERSION\" --architecture arm64", workflow)
        self.assertIn('--output "$RUNNER_TEMP/hypopg-base-target.json"', workflow)
        self.assertIn('resolve-core.sh "$RUNNER_TEMP/hypopg-base-target.json"', workflow)
        self.assertNotIn("hypopg_macos_pins", workflow)
        with self.assertRaisesRegex(emitter.coverage.CoverageError, "--target-config"):
            emitter._default_target()
        feasibility = Path("scripts/hypopg/macos-feasibility.sh").read_text()
        self.assertIn("target_config=${3:?usage:", feasibility)
        self.assertNotIn("hypopg_macos_pins", feasibility)

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

    def test_rejects_invalid_final_archive_pointer(self):
        self.fixture.extension.unlink()
        package = self.fixture.output / "payload"
        (package / "hypopg/LICENSES").mkdir(parents=True)
        (package / "hypopg/lib").mkdir()
        (package / "hypopg/lib/hypopg.dylib").write_bytes(b"native")
        pointer = license_pointer.write_pointer(package / "hypopg", "hypopg")
        pointer.write_text("wrong pointer\n")
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
        with self.assertRaisesRegex(Exception, "licence pointer"):
            self.fixture.emit()

    def test_checker_accepts_native_payload_with_exact_licence_pointer(self):
        from check_macos_extension_license_inventory import check_archive

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            package = base / "hypopg"
            (package / "share/extension").mkdir(parents=True)
            (package / "lib").mkdir()
            (package / "share/extension/hypopg.control").write_text("default_version = '1.4.3'\n")
            (package / "lib/hypopg.dylib").write_bytes(b"native fixture")
            license_pointer.write_pointer(package, "hypopg")
            with tarfile.open(base / "extension.tar.gz", "w:gz") as archive:
                archive.add(package, arcname="hypopg")
                metadata = base / "metadata.json"
                metadata.write_text(json.dumps({"project": "hypopg"}))
                archive.add(metadata, arcname="metadata.json")
            self.assertEqual(check_archive(base / "extension.tar.gz"), (1, 1))


if __name__ == "__main__":
    unittest.main()
