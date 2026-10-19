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
        postgis_profile = "postgis-publication-current-x86_64"
        registry["profiles"][postgis_profile] = {
            "scope": "publication", "platforms": ["linux-x86_64"],
            "case_ids": ["archive-suite"], "sources": ["postgis-profile.txt"],
        }
        (self.root / "postgis-profile.txt").write_text("historical importer fixture\n")
        (self.root / "support/verification-profiles.json").write_text(json.dumps(registry))
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
        self.vector_version = self._selected_version("pgvector", "18.6")
        self.postgis_version = self._selected_version("PostGIS", "18.6")
        self.core_name = f"postgresql-18.6-{self.platform}.tar.gz"
        self.vector_name = f"pgvector-{self.vector_version}-postgresql-18.6-{self.platform}.tar.gz"
        self.postgis_name = f"postgis-{self.postgis_version}-postgresql-18.6-{self.platform}.tar.gz"
        self.core_archive = self.core_dir / self.core_name
        self.vector_archive = self.core_dir / self.vector_name
        self.postgis_archive = self.postgis_dir / self.postgis_name
        self.core_archive.write_bytes(b"postgresql archive fixture")
        self.vector_archive.write_bytes(b"pgvector archive fixture")
        self._metadata_archive(self.postgis_archive, {
            "project": "postgis", "version": self.postgis_version, "postgresql_version": "18.6",
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

    def _selected_version(self, project, postgresql_version):
        support = coverage.load_json(self.root / "support.json")
        releases = coverage.release_snapshot(
            coverage.load_json(self.root / "support/postgresql-releases.json"), support)
        return importer._selected_extension_version(
            support, releases, project, postgresql_version, self.platform)

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
            postgis_profile, "PostGIS", self.postgis_version, "18.6", "18.6",
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
        vector_version = self._selected_version("pgvector", postgresql_version)
        vector = archives / f"pgvector-{vector_version}-postgresql-{postgresql_version}-{self.platform}.tar.gz"
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

    def _core_publication_artifact(self, postgresql_version="18.6", step_result="success",
                                   include_outputs=True):
        artifact = Path(self.temporary.name) / f"core-only-{postgresql_version}-{step_result}"
        archives = artifact / "pilot"
        publication = archives / "publication"
        records = publication / "records"
        records.mkdir(parents=True)
        core = archives / f"postgresql-{postgresql_version}-{self.platform}.tar.gz"
        core.write_bytes(f"core-only {postgresql_version}".encode())
        self._write_sidecar(core)
        profile_id = f"postgresql-publication-linux-{self.architecture}-{postgresql_version}"
        registry_path = self.root / "support/verification-profiles.json"
        registry = coverage.load_json(registry_path)
        registry["profiles"][profile_id] = {
            "scope": "publication", "platforms": [self.platform],
            "case_ids": ["archive-install"], "sources": ["core-only-profile.txt"],
        }
        (self.root / "core-only-profile.txt").write_text("core-only profile fixture\n")
        registry_path.write_text(json.dumps(registry))
        steps = publication / "current-steps.json"
        steps.write_text(json.dumps({"archive-install": step_result}))
        receipt = publication / "current-receipt.json"
        environ = {
            "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": self.run_id,
            "GITHUB_REPOSITORY": "example/repo", "GITHUB_SERVER_URL": "https://github.com",
        }
        core_receipts.create(
            self.root, archives, receipt, profile_id, postgresql_version,
            self.architecture, "current", "6.8.0-test-kernel", "Alpine Linux",
            "3.22.6", "sha256:" + "b" * 64, "linux-runtime-v1", "success",
            True, steps, environ=environ, publication_mode="core-only")
        core_emitter.emit(self.root, archives, receipt, records)
        if include_outputs:
            report = publication / "static-analysis/core.json"
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({
                "outcome": "passed", "architecture": self.architecture,
                "files": [{"path": "bin/postgres"}],
                "archives": [{"basename": core.name, "sha256": self._sha(core)}],
            }))
            symbols = archives / "debug-symbols"
            symbols.mkdir()
            (symbols / "index.json").write_text('{"symbols": ["postgres"]}\n')
            diagnostic = archives / "diagnostics/core"
            diagnostic.mkdir(parents=True)
            (diagnostic / "server.log").write_text("core-only diagnostic\n")
        return artifact

    def test_imports_explicit_core_only_publication_and_keeps_evidence_separate(self):
        artifact = self._core_publication_artifact()
        retained = importer.import_run(self.root, artifact, None, self.run_id,
                                       self.architecture, "18.6", "core-only")
        self.assertEqual(sum("/support/verification/" in f"/{path}" for path in retained), 1)
        evidence = (self.root / "support/evidence" /
                    f"linux-core-only-publication-{self.run_id}/postgresql-18.6/{self.architecture}")
        self.assertTrue((evidence / "static-analysis/core.json").is_file())
        self.assertTrue((evidence / "debug-symbols-index.json").is_file())
        self.assertTrue((evidence / "diagnostics/core/server.log").is_file())
        self.assertTrue((self.root / "support/evidence" /
                         f"linux-publication-{self.run_id}/x86_64").exists() is False)

    def test_same_run_retains_distinct_core_only_and_paired_postgresql_records(self):
        core_only = self._core_publication_artifact()
        importer.import_run(self.root, core_only, None, self.run_id,
                            self.architecture, "18.6", "core-only")
        importer.import_run(self.root, self.core_artifact, None, self.run_id,
                            self.architecture, "18.6")
        directory = self.root / "support/verification"
        prefix = f"postgresql-18.6-{self.platform}-current"
        core_record = directory / f"{prefix}-{self.run_id}.json"
        paired_record = directory / f"{prefix}-paired-{self.run_id}.json"
        self.assertEqual(core_record.read_bytes(), (core_only / "pilot/publication/records" /
                         core_record.name).read_bytes())
        self.assertEqual(paired_record.read_bytes(), (self.core_records /
                         core_record.name).read_bytes())
        self.assertEqual(json.loads(core_record.read_text())["profile_id"],
                         f"postgresql-publication-linux-{self.architecture}-18.6")
        self.assertEqual(json.loads(paired_record.read_text())["profile_id"],
                         f"linux-publication-current-{self.architecture}")

    def test_core_only_import_rejects_mode_confusion_and_conflicting_evidence(self):
        artifact = self._core_publication_artifact()
        receipt = artifact / "pilot/publication/current-receipt.json"
        data = json.loads(receipt.read_text())
        data["publication_mode"] = "paired"
        receipt.write_text(json.dumps(data))
        with self.assertRaisesRegex(coverage.CoverageError, "publication mode"):
            importer.import_run(self.root, artifact, None, self.run_id,
                                self.architecture, "18.6", "core-only")
        data["publication_mode"] = "core-only"
        receipt.write_text(json.dumps(data))
        target = (self.root / "support/evidence" /
                  f"linux-core-only-publication-{self.run_id}/postgresql-18.6/{self.architecture}/static-analysis/core.json")
        target.parent.mkdir(parents=True)
        target.write_text("conflicting report\n")
        with self.assertRaisesRegex(coverage.CoverageError, "refusing to replace"):
            importer.import_run(self.root, artifact, None, self.run_id,
                                self.architecture, "18.6", "core-only")

    def test_failed_and_skipped_core_only_attempts_import_without_downstream_outputs(self):
        for outcome in ("failure", "skipped"):
            with self.subTest(outcome=outcome):
                self.run_id = "7654321" if outcome == "failure" else "7654322"
                artifact = self._core_publication_artifact(step_result=outcome,
                                                           include_outputs=False)
                retained = importer.import_run(self.root, artifact, None, self.run_id,
                                               self.architecture, "18.6", "core-only")
                self.assertEqual(sum("/support/verification/" in f"/{path}" for path in retained), 1)
                evidence = (self.root / "support/evidence" /
                            f"linux-core-only-publication-{self.run_id}/postgresql-18.6/{self.architecture}")
                self.assertTrue((evidence / "current-receipt.json").is_file())
                self.assertFalse((evidence / "debug-symbols-index.json").exists())
                self.assertFalse((evidence / "static-analysis/core.json").exists())

    def test_passed_core_only_attempt_requires_static_symbol_and_diagnostic_outputs(self):
        artifact = self._core_publication_artifact(include_outputs=False)
        archives = artifact / "pilot"
        core = archives / f"postgresql-18.6-{self.platform}.tar.gz"
        report = archives / "publication/static-analysis/core.json"
        with self.assertRaisesRegex(coverage.CoverageError, "requires a static-analysis report"):
            importer.import_run(self.root, artifact, None, self.run_id,
                                self.architecture, "18.6", "core-only")
        report.parent.mkdir(parents=True)
        report.write_text(json.dumps({
            "outcome": "passed", "architecture": self.architecture,
            "files": [{"path": "bin/postgres"}],
            "archives": [{"basename": core.name, "sha256": self._sha(core)}],
        }))
        with self.assertRaisesRegex(coverage.CoverageError, "requires a debug-symbol index"):
            importer.import_run(self.root, artifact, None, self.run_id,
                                self.architecture, "18.6", "core-only")
        symbols = archives / "debug-symbols"
        symbols.mkdir()
        (symbols / "index.json").write_text('{"symbols": []}\n')
        with self.assertRaisesRegex(coverage.CoverageError, "requires diagnostics evidence"):
            importer.import_run(self.root, artifact, None, self.run_id,
                                self.architecture, "18.6", "core-only")
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
                self.assertTrue(any(name.startswith(f"pgvector-{self._selected_version('pgvector', version)}-postgresql-{version}-")
                                    for name in core_records))
                evidence = self.root / "support/evidence" / f"linux-publication-{self.run_id}"
                if version == "18.6":
                    evidence /= self.architecture
                else:
                    evidence = evidence / f"postgresql-{version}" / self.architecture
                self.assertTrue((evidence / "current-receipt.json").is_file())

    def test_imports_postgis_against_selected_pg17_core(self):
        version = "17.11"
        postgis_version = self._selected_version("PostGIS", version)
        core_artifact, postgis_artifact = self._postgis_artifact_for_core(version, postgis_version)
        retained = importer.import_run(self.root, core_artifact, postgis_artifact,
                                       self.run_id, self.architecture, version)
        self.assertEqual(sum("/support/verification/" in f"/{path}" for path in retained), 6)
        self.assertTrue((self.root / "support/verification" /
                         f"postgis-{postgis_version}-postgresql-{version}-{self.platform}-current-{self.run_id}.json").is_file())

    def _postgis_artifact_for_core(self, version, postgis_version):
        core_artifact = self._core_only_artifact(version)
        postgis_artifact = Path(self.temporary.name) / f"postgis-{version}"
        extension_dir = postgis_artifact / "postgis"
        publication = postgis_artifact / "postgis-publication"
        records = publication / "records"
        records.mkdir(parents=True)
        archive = extension_dir / f"postgis-{postgis_version}-postgresql-{version}-{self.platform}.tar.gz"
        extension_dir.mkdir()
        self._metadata_archive(archive, {
            "project": "postgis", "version": postgis_version, "postgresql_version": version,
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
            profile_id, "PostGIS", postgis_version, version, version,
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
        return core_artifact, postgis_artifact

    def test_importer_uses_alternate_versions_selected_in_support(self):
        support_path = self.root / "support.json"
        support = coverage.load_json(support_path)
        support["extensions"]["pgvector"]["versions"] = {
            "0.8.8": {"postgresql_minimum_major": 15}}
        support["extensions"]["PostGIS"]["versions"] = {
            "3.6.5": {"postgresql_minimum_major": 15, "postgresql_maximum_major": 18}}
        support_path.write_text(json.dumps(support), encoding="utf-8")
        self.assertEqual(self._selected_version("pgvector", "17.11"), "0.8.8")
        self.assertEqual(self._selected_version("PostGIS", "17.11"), "3.6.5")

        self.run_id = "7654322"
        artifact, postgis_artifact = self._postgis_artifact_for_core("17.11", "3.6.5")
        retained = importer.import_run(
            self.root, artifact, postgis_artifact, self.run_id, self.architecture, "17.11")
        self.assertTrue(any(Path(path).name.startswith(
            f"pgvector-0.8.8-postgresql-17.11-{self.platform}-current-") for path in retained))
        self.assertTrue(any(Path(path).name.startswith(
            f"postgis-3.6.5-postgresql-17.11-{self.platform}-current-") for path in retained))

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
