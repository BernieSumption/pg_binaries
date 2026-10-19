import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import coverage
import create_extension_publication_receipt as receipt_creator
import emit_extension_publication_records as emitter
import import_linux_postgis_publication as importer
import linux_core_resolution


class LinuxPostgisPublicationImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "root"
        for source in ("support.json", "support/verification-profiles.json",
                       "support/postgresql-releases.json"):
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / source, destination)
        profiles = coverage.load_json(self.root / "support/verification-profiles.json")["profiles"]
        profile = profiles["postgis-publication-linux-x86_64-17.11"]
        for profile_source in profile["sources"]:
            source = profile_source.partition("#profile-section=")[0]
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / source, destination)

        self.run_id = "7654321"
        self.pg = "17.11"
        self.architecture = "x86_64"
        self.platform = f"linux-{self.architecture}"
        self.core_artifact = self.base / "core-artifact"
        self.postgis_artifact = self.base / "postgis-artifact"
        self.core_dir = self.core_artifact / "pilot"
        self.extension_dir = self.postgis_artifact / "postgis"
        self.publication = self.postgis_artifact / "postgis-publication"
        self.records_dir = self.publication / "records"
        self.core_name = f"postgresql-{self.pg}-{self.platform}.tar.gz"
        self.extension_name = f"postgis-3.6.4-postgresql-{self.pg}-{self.platform}.tar.gz"
        self.core_dir.mkdir(parents=True)
        self.extension_dir.mkdir(parents=True)
        self.records_dir.mkdir(parents=True)
        self._make_archives()
        self._make_publication()

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    @staticmethod
    def _tar_json(path, members):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(path, "w:gz") as archive:
            for name, value in members.items():
                data = json.dumps(value, sort_keys=True).encode()
                from io import BytesIO
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, BytesIO(data))

    def _write_sidecar(self, path):
        path.with_name(path.name + ".sha256").write_text(
            f"{self._sha(path)}  {path.name}\n", encoding="utf-8")

    def _make_archives(self):
        manifest = {
            "component": "postgresql", "version": self.pg,
            "platform": "linux", "architecture": self.architecture,
            "source_revision": "a" * 40, "build_id": "test-build",
            "builder_inputs": {
                "base_image": "ubuntu:22.04", "base_image_digest": "sha256:" + "b" * 64,
                "packages_sha256": "c" * 64,
            },
        }
        self._tar_json(self.core_dir / self.core_name, {
            "postgresql/manifest.json": manifest,
            "postgresql/bin/pg_config": {"test": True},
        })
        self._write_sidecar(self.core_dir / self.core_name)
        support = coverage.load_json(self.root / "support.json")["extensions"]["PostGIS"]
        self._tar_json(self.extension_dir / self.extension_name, {
            "metadata.json": {
                "project": "postgis", "version": "3.6.4",
                "sql_names": support["sql_names"], "requires": [],
                "postgresql_version": self.pg, "platform": "linux",
                "architecture": self.architecture,
            },
        })
        self._write_sidecar(self.extension_dir / self.extension_name)
        self.core_resolution = linux_core_resolution.create_record(
            self.core_dir / self.core_name, self.pg, self.architecture, "built",
            environ={
                "GITHUB_RUN_ID": self.run_id, "GITHUB_RUN_ATTEMPT": "1",
                "GITHUB_REPOSITORY": "example/repo", "GITHUB_WORKFLOW_REF": "example/repo/.github/workflows/test.yml@refs/heads/test",
                "GITHUB_SHA": "a" * 40,
            })
        (self.core_dir / "core-resolution.json").write_text(
            json.dumps(self.core_resolution), encoding="utf-8")
        report_archives = [
            {"basename": self.core_name, "sha256": self._sha(self.core_dir / self.core_name)},
            {"basename": self.extension_name, "sha256": self._sha(self.extension_dir / self.extension_name)},
        ]
        report_dir = self.extension_dir / "static-analysis"
        report_dir.mkdir()
        (report_dir / "postgis.json").write_text(json.dumps({
            "outcome": "passed", "architecture": self.architecture,
            "files": [{"path": "postgis/lib/postgis-3.so", "architecture": self.architecture,
                       "interpreter": "none", "runtime_search_paths": []}],
            "archives": report_archives,
        }))

    def _make_publication(self):
        profile_id = f"postgis-publication-linux-{self.architecture}-{self.pg}"
        profile = coverage.verification_profile(self.root, profile_id)
        self.steps = {profile["case_ids"][0]: "success"}
        steps_path = self.publication / "current-steps.json"
        steps_path.write_text(json.dumps(self.steps), encoding="utf-8")
        receipt_path = self.publication / "current-receipt.json"
        receipt_creator.create(
            self.root, self.extension_dir, self.core_dir, receipt_path,
            profile_id, "PostGIS", "3.6.4", self.pg, self.pg,
            self.architecture, "current", "6.8.0-test-kernel", "Alpine Linux", "3.22.6",
            "sha256:" + "d" * 64, "success", True, steps_path,
            environ={
                "GITHUB_SHA": "e" * 40, "GITHUB_RUN_ID": self.run_id,
                "GITHUB_REPOSITORY": "example/repo", "GITHUB_SERVER_URL": "https://github.com",
            })
        emitter.emit(self.root, self.extension_dir, self.core_dir, receipt_path, self.records_dir)

    def _import(self):
        return importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                   self.run_id, self.architecture, self.pg)

    def test_imports_four_components_with_exact_core_and_versioned_evidence(self):
        retained = self._import()
        evidence = (self.root / "support/evidence" / f"postgis-publication-{self.run_id}"
                    / self.architecture / self.pg)
        self.assertTrue((evidence / "current-receipt.json").is_file())
        self.assertTrue((evidence / "core-resolution.json").is_file())
        self.assertEqual(len(list((self.root / "support/verification").glob("*.json"))), 4)
        expected_sha = self._sha(self.core_dir / self.core_name)
        for path in (self.root / "support/verification").glob("*.json"):
            record = json.loads(path.read_text())
            self.assertEqual(record["assembled_core"], {
                "archive": self.core_name, "sha256": expected_sha, "version": self.pg})
        self.assertEqual(self._import(), retained)

    def test_rejects_missing_component_record(self):
        next(self.records_dir.glob("postgis_raster-*.json")).unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "exactly four"):
            self._import()
        self.assertFalse((self.root / "support/evidence").exists())

    def test_rejects_core_archive_byte_mismatch(self):
        archive = self.core_dir / self.core_name
        archive.write_bytes(archive.read_bytes() + b"tamper")
        self._write_sidecar(archive)
        with self.assertRaisesRegex(coverage.CoverageError, "core provenance"):

            self._import()
        self.assertFalse((self.root / "support/evidence").exists())

    def test_rejects_receipt_profile_or_target_mismatch(self):
        path = self.publication / "current-receipt.json"
        receipt = json.loads(path.read_text())
        receipt["profile_id"] = "postgis-publication-linux-arm64-17.11"
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(coverage.CoverageError, "receipt identity"):
            self._import()
        self.assertFalse((self.root / "support/evidence").exists())


if __name__ == "__main__":
    unittest.main()
