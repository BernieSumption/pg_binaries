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
import create_extension_publication_receipt as extension_receipts
import create_linux_publication_receipt as core_receipts
import emit_extension_publication_records as extension_emitter
import emit_linux_publication_records as core_emitter
import import_linux_publication_run as importer


class LinuxPublicationRunImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.root = base / "root"
        (self.root / "support").mkdir(parents=True)
        for source in ("support.json", "support/verification-profiles.json",
                       "support/postgresql-releases.json"):
            destination = self.root / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / source, destination)
        registry = coverage.load_json(self.root / "support/verification-profiles.json")
        source_paths = set()
        for profile_id, profile in registry["profiles"].items():
            if profile_id.startswith(("linux-publication-", "postgis-publication-")):
                source_paths.update(profile["sources"])
        for source in source_paths:
            source_path = source.partition("#profile-section=")[0]
            destination = self.root / source_path
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(REPO / source_path, destination)

        self.core_artifact = base / "core-artifact"
        self.postgis_artifact = base / "postgis-artifact"
        self.core_dir = self.core_artifact / "pilot"
        self.core_publication = self.core_dir / "publication"
        self.postgis_dir = self.postgis_artifact / "postgis"
        self.postgis_publication = self.postgis_artifact / "postgis-publication"
        self.core_records = self.core_publication / "records"
        self.postgis_records = self.postgis_publication / "records"
        for directory in (self.core_records, self.postgis_records, self.postgis_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self.run_id = "7654321"
        self.architecture = "x86_64"
        self.platform = "linux-x86_64"
        self.core_name = f"postgresql-18.6-{self.platform}.tar.gz"
        self.vector_name = f"pgvector-0.8.7-postgresql-18.6-{self.platform}.tar.gz"
        self.postgis_name = f"postgis-3.6.4-postgresql-18.6-{self.platform}.tar.gz"
        self.core_archive = self.core_dir / self.core_name
        self.vector_archive = self.core_dir / self.vector_name
        self.postgis_archive = self.postgis_dir / self.postgis_name
        self.core_archive.write_bytes(b"postgresql archive fixture")
        self.vector_archive.write_bytes(b"pgvector archive fixture")
        self._metadata_archive(self.postgis_archive, {
            "project": "postgis", "version": "3.6.4", "postgresql_version": "18.6",
            "platform": "linux", "architecture": "x86_64",
            "sql_names": coverage.load_json(self.root / "support.json")["extensions"]["PostGIS"]["sql_names"],
            "requires": [],
        })
        for archive in (self.core_archive, self.vector_archive, self.postgis_archive):
            self._write_sidecar(archive)
        self._make_records()
        for directory, filename, archives in (
                (self.core_dir / "publication", "core-pgvector.json", (self.core_archive, self.vector_archive)),
                (self.postgis_dir, "postgis.json", (self.core_archive, self.postgis_archive))):
            analysis = directory / "static-analysis" / filename
            analysis.parent.mkdir(parents=True, exist_ok=True)
            analysis.write_text(json.dumps({"outcome": "passed", "architecture": self.architecture,
                "files": [{"path": "metadata.json", "architecture": self.architecture,
                           "interpreter": "none", "runtime_search_paths": []}], "archives": [
                    {"basename": item.name, "sha256": self._sha(item)} for item in archives]}))
        self._write_symbol_indexes()
        diagnostic = self.core_dir / "diagnostics/postgresql-error"
        diagnostic.mkdir(parents=True)
        (diagnostic / "server.log").write_text("controlled server diagnostic\n")

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    @classmethod
    def _write_sidecar(cls, archive):
        archive = Path(archive)
        archive.with_name(archive.name + ".sha256").write_text(
            f"{cls._sha(archive)}  {archive.name}\n", encoding="utf-8")

    @staticmethod
    def _metadata_archive(path, metadata):
        temporary = Path(path).with_suffix(".json")
        temporary.write_text(json.dumps(metadata), encoding="utf-8")
        with tarfile.open(path, "w:gz") as archive:
            archive.add(temporary, arcname="metadata.json")
        temporary.unlink()

    def _make_records(self):
        revision = "a" * 40
        environ = {
            "GITHUB_SHA": revision, "GITHUB_RUN_ID": self.run_id,
            "GITHUB_REPOSITORY": "example/repo", "GITHUB_SERVER_URL": "https://github.com",
        }
        endpoint = "current"
        kernel = "6.8.0-test-kernel"
        distribution = "Alpine Linux"
        image = "sha256:" + "b" * 64
        core_profile = f"linux-publication-{endpoint}-{self.architecture}"
        core_steps = self.core_publication / f"{endpoint}-steps.json"
        core_steps.write_text(json.dumps({case: "success" for case in
            coverage.verification_profile(self.root, core_profile)["case_ids"]}), encoding="utf-8")
        core_receipt_path = self.core_publication / f"{endpoint}-receipt.json"
        core_receipts.create(
            self.root, self.core_dir, core_receipt_path, core_profile, "18.6",
            self.architecture, endpoint, kernel, distribution,
            "3.22.6", image,
            "linux-runtime-v1", "success", True, core_steps, environ=environ)
        core_emitter.emit(self.root, self.core_dir, core_receipt_path, self.core_records)

        postgis_profile = f"postgis-publication-{endpoint}-{self.architecture}"
        postgis_steps = self.postgis_publication / f"{endpoint}-steps.json"
        postgis_steps.write_text(json.dumps({case: "success" for case in
            coverage.verification_profile(self.root, postgis_profile)["case_ids"]}), encoding="utf-8")
        postgis_receipt_path = self.postgis_publication / f"{endpoint}-receipt.json"
        extension_receipts.create(
            self.root, self.postgis_dir, self.core_dir, postgis_receipt_path,
            postgis_profile, "PostGIS", "3.6.4", "18.6", "18.6",
            self.architecture, endpoint, kernel, distribution,
            "3.22.6", image,
            "success", True, postgis_steps, environ=environ,
            prerequisite_archives={})
        extension_emitter.emit(self.root, self.postgis_dir, self.core_dir,
                                postgis_receipt_path, self.postgis_records, {})

    def _write_symbol_indexes(self):
        for directory in (self.core_dir / "debug-symbols", self.postgis_dir / "debug-symbols"):
            directory.mkdir(parents=True)
            (directory / "index.json").write_text("{\"symbols\": []}\n", encoding="utf-8")

    def test_imports_current_profile_records_and_compact_evidence_idempotently(self):
        retained = importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                       self.run_id, self.architecture)
        self.assertEqual(len(list((self.root / "support/verification").glob(f"*-{self.run_id}.json"))), 6)
        core_evidence = self.root / "support/evidence" / f"linux-publication-{self.run_id}/x86_64"
        postgis_evidence = self.root / "support/evidence" / f"postgis-publication-{self.run_id}/x86_64"
        self.assertTrue((core_evidence / "debug-symbols-index.json").is_file())
        self.assertTrue((core_evidence / "diagnostics/postgresql-error/server.log").is_file())
        self.assertTrue((postgis_evidence / "current-receipt.json").is_file())
        receipt = json.loads((core_evidence / "current-receipt.json").read_text())
        self.assertEqual(receipt["distribution_version"], "3.22.6")
        self.assertFalse(any(".tar.gz" in path for path in retained))
        first = (core_evidence / "current-receipt.json").read_bytes()
        importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                            self.run_id, self.architecture)
        self.assertEqual((core_evidence / "current-receipt.json").read_bytes(), first)

    def test_retains_raw_step_outcomes_when_archives_and_receipts_are_absent(self):
        for path in (*self.core_records.glob("*.json"), *self.postgis_records.glob("*.json")):
            path.unlink()
        for publication in (self.core_publication, self.postgis_publication):
            (publication / "current-receipt.json").unlink()
        for archive in (self.core_archive, self.vector_archive, self.postgis_archive):
            archive.unlink()
            archive.with_name(archive.name + ".sha256").unlink()
        retained = importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                       self.run_id, self.architecture)
        self.assertEqual(len(retained), 2)
        self.assertTrue((self.root / "support/evidence" / f"linux-publication-{self.run_id}/x86_64/current-steps.json").is_file())
        self.assertTrue((self.root / "support/evidence" / f"postgis-publication-{self.run_id}/x86_64/current-steps.json").is_file())

    def test_rejects_sidecar_and_non_alpine_receipt(self):
        sidecar = self.core_archive.with_name(self.core_name + ".sha256")
        sidecar.write_text(f"{'0' * 64}  {self.core_name}\n", encoding="utf-8")
        with self.assertRaisesRegex(coverage.CoverageError, "checksum does not match"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.run_id, self.architecture)
        self._write_sidecar(self.core_archive)
        receipt_path = self.core_publication / "current-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["distribution"] = "Ubuntu"
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(coverage.CoverageError, "Alpine 3.22"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.run_id, self.architecture)

    def test_rejects_step_receipt_disagreement_and_differing_retained_evidence(self):
        steps = self.core_publication / "current-steps.json"
        data = json.loads(steps.read_text())
        data["diagnostics"] = "failure"
        steps.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(coverage.CoverageError, "receipt identity or outcomes"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.run_id, self.architecture)
        steps.write_text(json.dumps({case: "success" for case in
            coverage.verification_profile(self.root, "linux-publication-current-x86_64")["case_ids"]}), encoding="utf-8")
        target = self.root / "support/evidence" / f"linux-publication-{self.run_id}/x86_64/current-steps.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("different evidence\n", encoding="utf-8")
        with self.assertRaisesRegex(coverage.CoverageError, "refusing to replace"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.run_id, self.architecture)

    def test_rejects_invalid_run_identity_and_record_checksum(self):
        with self.assertRaisesRegex(coverage.CoverageError, "run_id"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                "bad-run", self.architecture)
        with self.assertRaisesRegex(coverage.CoverageError, "architecture"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.run_id, "riscv64")
        record_path = next(self.core_records.glob(f"*-current-{self.run_id}.json"))
        record = json.loads(record_path.read_text())
        record["sha256"] = "0" * 64
        record_path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(coverage.CoverageError, "archive checksum does not match"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.run_id, self.architecture)

    def test_static_analysis_report_is_retained_and_archive_claims_are_exact(self):
        importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                            self.run_id, self.architecture)
        retained = self.root / "support/evidence" / f"linux-publication-{self.run_id}/x86_64/static-analysis/core-pgvector.json"
        self.assertTrue(retained.is_file())
        report = self.core_dir / "publication/static-analysis/core-pgvector.json"
        data = json.loads(report.read_text())
        data["archives"].pop()
        report.write_text(json.dumps(data))
        with self.assertRaisesRegex(coverage.CoverageError, "archives do not match"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.run_id, self.architecture)

    def test_passed_publication_requires_static_analysis_report(self):
        (self.postgis_dir / "static-analysis/postgis.json").unlink()
        with self.assertRaisesRegex(coverage.CoverageError, "requires a static-analysis report"):
            importer.import_run(self.root, self.core_artifact, self.postgis_artifact,
                                self.run_id, self.architecture)

    def _core_only_artifact(self, postgresql_version):
        artifact = Path(self.temporary.name) / f"core-{postgresql_version}"
        archives = artifact / "pilot"
        publication = archives / "publication"
        records = publication / "records"
        records.mkdir(parents=True)
        core = archives / f"postgresql-{postgresql_version}-{self.platform}.tar.gz"
        vector = archives / f"pgvector-{importer.VECTOR_VERSION}-postgresql-{postgresql_version}-{self.platform}.tar.gz"
        core.write_bytes(f"core {postgresql_version}".encode())
        vector.write_bytes(f"vector {postgresql_version}".encode())
        for archive in (core, vector):
            self._write_sidecar(archive)
        profile_id = f"linux-publication-current-{self.architecture}"
        steps = publication / "current-steps.json"
        profile = coverage.verification_profile(self.root, profile_id)
        steps.write_text(json.dumps({case: "success" for case in profile["case_ids"]}))
        receipt = publication / "current-receipt.json"
        environ = {
            "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": self.run_id,
            "GITHUB_REPOSITORY": "example/repo", "GITHUB_SERVER_URL": "https://github.com",
        }
        core_receipts.create(
            self.root, archives, receipt, profile_id, postgresql_version,
            self.architecture, "current", "6.8.0-test-kernel", "Alpine Linux",
            "3.22.6", "sha256:" + "b" * 64, "linux-runtime-v1", "success",
            True, steps, environ=environ)
        core_emitter.emit(self.root, archives, receipt, records)
        report = publication / "static-analysis/core-pgvector.json"
        report.parent.mkdir(parents=True)
        report.write_text(json.dumps({
            "outcome": "passed", "architecture": self.architecture,
            "files": [{"path": "metadata.json"}],
            "archives": [{"basename": archive.name, "sha256": self._sha(archive)}
                         for archive in (core, vector)],
        }))
        return artifact

    def test_imports_core_and_pgvector_for_each_selected_core_without_postgis(self):
        for version in ("15.19", "16.15", "17.11", "18.6"):
            with self.subTest(postgresql_version=version):
                self.run_id = "7654321"
                artifact = self._core_only_artifact(version)
                retained = importer.import_run(
                    self.root, artifact, None, self.run_id, self.architecture, version)
                core_records = [Path(path).name for path in retained
                                if "/support/verification/" in f"/{path}"]
                self.assertEqual(len(core_records), 2)
                self.assertTrue(any(name.startswith(f"postgresql-{version}-")
                                    for name in core_records))
                self.assertTrue(any(name.startswith(f"pgvector-{importer.VECTOR_VERSION}-postgresql-{version}-")
                                    for name in core_records))
                evidence = self.root / "support/evidence" / f"linux-publication-{self.run_id}"
                if version == "18.6":
                    evidence /= self.architecture
                else:
                    evidence = evidence / f"postgresql-{version}" / self.architecture
                self.assertTrue((evidence / "current-receipt.json").is_file())

    def test_imports_postgis_against_selected_pg17_core(self):
        version = "17.11"
        core_artifact = self._core_only_artifact(version)
        postgis_artifact = Path(self.temporary.name) / "postgis-17.11"
        extension_dir = postgis_artifact / "postgis"
        publication = postgis_artifact / "postgis-publication"
        records = publication / "records"
        records.mkdir(parents=True)
        archive = extension_dir / f"postgis-3.6.4-postgresql-{version}-{self.platform}.tar.gz"
        extension_dir.mkdir()
        self._metadata_archive(archive, {
            "project": "postgis", "version": "3.6.4", "postgresql_version": version,
            "platform": "linux", "architecture": self.architecture,
            "sql_names": coverage.load_json(self.root / "support.json")["extensions"]["PostGIS"]["sql_names"],
            "requires": [],
        })
        self._write_sidecar(archive)
        profile_id = f"postgis-publication-current-{self.architecture}"
        steps = publication / "current-steps.json"
        profile = coverage.verification_profile(self.root, profile_id)
        steps.write_text(json.dumps({case: "success" for case in profile["case_ids"]}))
        receipt = publication / "current-receipt.json"
        environ = {
            "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": self.run_id,
            "GITHUB_REPOSITORY": "example/repo", "GITHUB_SERVER_URL": "https://github.com",
        }
        extension_receipts.create(
            self.root, extension_dir, core_artifact / "pilot", receipt,
            profile_id, "PostGIS", "3.6.4", version, version,
            self.architecture, "current", "6.8.0-test-kernel", "Alpine Linux",
            "3.22.6", "sha256:" + "b" * 64, "success", True, steps,
            environ=environ, prerequisite_archives={})
        extension_emitter.emit(self.root, extension_dir, core_artifact / "pilot",
                               receipt, records, {})
        report = extension_dir / "static-analysis/postgis.json"
        report.parent.mkdir(parents=True)
        core = core_artifact / "pilot" / f"postgresql-{version}-{self.platform}.tar.gz"
        report.write_text(json.dumps({
            "outcome": "passed", "architecture": self.architecture,
            "files": [{"path": "metadata.json"}],
            "archives": [{"basename": item.name, "sha256": self._sha(item)}
                         for item in (core, archive)],
        }))
        retained = importer.import_run(self.root, core_artifact, postgis_artifact,
                                       self.run_id, self.architecture, version)
        self.assertEqual(sum("/support/verification/" in f"/{path}" for path in retained), 6)
        self.assertTrue((self.root / "support/verification" /
                         f"postgis-3.6.4-postgresql-{version}-{self.platform}-current-{self.run_id}.json").is_file())

    def test_rejects_unselected_postgresql_minor(self):
        with self.assertRaisesRegex(coverage.CoverageError, "18.5.*not selected"):
            importer.import_run(self.root, self.core_artifact, None,
                                self.run_id, self.architecture, "18.5")

    def test_18_6_core_import_can_omit_postgis_artifact(self):
        self.run_id = "7654321"
        artifact = self._core_only_artifact("18.6")
        retained = importer.import_run(
            self.root, artifact, None, self.run_id, self.architecture, "18.6")
        self.assertEqual(sum("/support/verification/" in f"/{path}" for path in retained), 2)


if __name__ == "__main__":
    unittest.main()
