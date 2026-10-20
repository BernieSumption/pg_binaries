"""Focused checks for Linux pg_jsonschema candidate evidence helpers."""

import hashlib
import io
import json
import sys
import tempfile
import tarfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import emit_pg_jsonschema_linux_publication as publication
import import_pg_jsonschema_linux_publication as importer
import coverage
import linux_core_resolution


class LinuxPublicationHelpers(unittest.TestCase):
    def _core_resolution_fixture(self, directory, origin="built", pg_version="18.6", architecture="x86_64"):
        base = Path(directory)
        core_dir = base / "core"
        core_dir.mkdir(exist_ok=True)
        core = core_dir / f"postgresql-{pg_version}-linux-{architecture}.tar.gz"
        manifest = {
            "component": "postgresql", "version": pg_version, "platform": "linux",
            "architecture": architecture, "source_revision": "e" * 40, "build_id": "linux-core-1",
            "builder_inputs": {"base_image": "ubuntu:22.04", "base_image_digest": "sha256:" + "f" * 64,
                               "packages_sha256": "a" * 64},
        }
        with tarfile.open(core, "w:gz") as archive:
            payload = json.dumps(manifest).encode()
            member = tarfile.TarInfo("postgresql/manifest.json")
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        provenance = {"source_revision": "e" * 40, "build_id": "linux-core-1",
                      "build_inputs": manifest["builder_inputs"], "provider": "github-actions",
                      "run_id": "12345", "run_attempt": 1}
        if origin == "built":
            provenance.update({"run_sha": "c" * 40, "repository": "owner/repo",
                               "workflow_ref": "owner/repo/.github/workflows/core.yml@refs/heads/spike"})
        else:
            provenance.update({"artifact_name": "postgresql-linux-x86_64", "head_sha": "d" * 40})
        record = {"schema_version": 1, "archive": core.name, "sha256": hashlib.sha256(core.read_bytes()).hexdigest(),
                  "postgresql_version": pg_version, "architecture": architecture, "origin": origin,
                  "provenance": provenance}
        resolution_path = base / "core-resolution.json"
        resolution_path.write_text(json.dumps(record), encoding="utf-8")
        return core_dir, resolution_path, record

    def test_dynamic_built_core_resolution_is_recorded_and_bound_to_run(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archives = base / "archives"
            archives.mkdir()
            core_dir, resolution_path, resolution = self._core_resolution_fixture(base)
            profile = {"profile_revision": "b" * 64, "case_ids": list(publication.CASES)}
            with patch.object(coverage, "verification_profile", return_value=profile):
                paths = publication.emit(ROOT, archives, core_dir, archives / "publication", "x86_64",
                                         "failure", "skipped", "c" * 40, "12345", "owner/repo",
                                         "https://github.com", "image", "6.17.0-azure",
                                         core_resolution_path=resolution_path)
            attempt = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertEqual(attempt["core_resolution"], resolution)
            self.assertEqual(attempt["core_origin"], "built")
            self.assertEqual(attempt["core_provenance"], resolution["provenance"])
            self.assertEqual(attempt["core_run_id"], "12345")
            self.assertEqual(json.loads((archives / "publication/core-resolution.json").read_text()), resolution)
            with patch.object(coverage, "verification_profile", return_value=profile), \
                    self.assertRaises(coverage.CoverageError):
                publication.emit(ROOT, archives, core_dir, archives / "mismatch", "x86_64",
                                 "failure", "skipped", "b" * 40, "12345", "owner/repo",
                                 "https://github.com", "image", "6.17.0-azure",
                                 core_resolution_path=resolution_path)

    def test_emitter_rejects_missing_core_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with self.assertRaisesRegex(coverage.CoverageError, "core-resolution.json is required"):
                publication.emit(ROOT, base, base, base / "publication", "x86_64", "failure", "skipped",
                                 "c" * 40, "12345", "owner/repo", "https://github.com", "image",
                                 "6.17.0-azure")

    def test_dynamic_reused_resolution_accepts_checked_producer_run(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archives = base / "archives"
            archives.mkdir()
            core_dir, resolution_path, resolution = self._core_resolution_fixture(base, "reused")
            profile = {"profile_revision": "b" * 64, "case_ids": list(publication.CASES)}
            with patch.object(coverage, "verification_profile", return_value=profile):
                attempt_path, = publication.emit(ROOT, archives, core_dir, archives / "publication", "x86_64",
                                                 "failure", "skipped", "c" * 40, "99999", "owner/repo",
                                                 "https://github.com", "image", "6.17.0-azure",
                                                 core_resolution_path=resolution_path)
            attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
            self.assertEqual(attempt["core_origin"], "reused")
            self.assertEqual(attempt["core_provenance"]["run_id"], "12345")
            self.assertEqual(attempt["core_resolution"], resolution)

    def test_evidence_directory_discriminates_postgresql_version(self):
        root = Path("/repo")
        pg15 = importer._evidence_directory(root, "39113295355", "15.19", "x86_64")
        pg16 = importer._evidence_directory(root, "39113295355", "16.15", "x86_64")
        arm64 = importer._evidence_directory(root, "39113295355", "15.19", "arm64")
        self.assertEqual(pg15, root / "support/evidence/pg_jsonschema-linux-publication-39113295355/15.19/x86_64")
        self.assertNotEqual(pg15, pg16)
        self.assertNotEqual(pg15, arm64)

    def test_architecture_profiles_are_scoped(self):
        self.assertEqual(publication.profile_id("x86_64", "18.6"),
                         "pg-jsonschema-publication-linux-x86_64-18.6")
        self.assertEqual(publication.profile_id("x86_64", "17.11"),
                         "pg-jsonschema-publication-linux-x86_64-17.11")
        self.assertNotEqual(publication.profile_id("x86_64", "18.6"),
                            publication.profile_id("arm64", "18.6"))

    def test_postgresql_versions_follow_supported_release_snapshot(self):
        expected = tuple(coverage.release_snapshot(
            coverage.load_json(ROOT / "support/postgresql-releases.json"),
            coverage.load_json(ROOT / "support.json")))
        self.assertEqual(publication.pg_versions(ROOT), expected)

    def test_step_outcomes_are_mapped(self):
        self.assertEqual(publication._step("success"), "passed")
        self.assertEqual(publication._step("failure"), "failed")
        self.assertEqual(publication._step("cancelled"), "skipped")
        with self.assertRaises(coverage.CoverageError):
            publication._step("unexpected")

    def test_verify_failure_marks_sql_skipped_when_elf_check_failed(self):
        self.assertEqual(publication._case_results("failure", "failed"), ("skipped", "failure"))
        self.assertEqual(publication._case_results("failure", "passed"), ("failure", "success"))
        self.assertEqual(publication._case_results("success", "passed"), ("success", "success"))

    def test_failed_build_still_emits_iterable_raw_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            archives = Path(directory) / "archives"
            core_dir = Path(directory) / "core"
            output = archives / "publication"
            archives.mkdir()
            core_dir.mkdir()
            profile = {"profile_revision": "b" * 64, "case_ids": list(publication.CASES)}
            core_dir, resolution_path, resolution = self._core_resolution_fixture(
                archives.parent, architecture="arm64")
            with patch.object(coverage, "verification_profile", return_value=profile):
                paths = publication.emit(ROOT, archives, core_dir, output, "arm64", "failure", "skipped",
                                         "c" * 40, "12345", "owner/repo", "https://github.com", "image",
                                         "6.17.0-azure", core_resolution_path=resolution_path)
            self.assertEqual(paths, (output / "attempt.json",))
            attempt = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertEqual(attempt["workflow_steps"], {"build": "failure", "verify": "skipped"})
            self.assertEqual(attempt["steps"], {"archive-suite": "skipped", "elf-closure": "skipped"})

    def test_postgresql_17_attempt_uses_its_profile_and_resolved_core(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archives, core_dir = root / "archives", root / "core"
            archives.mkdir()
            core_dir, resolution_path, resolution = self._core_resolution_fixture(root, pg_version="17.11")
            profile = {"profile_revision": "b" * 64, "case_ids": list(publication.CASES)}
            with patch.object(coverage, "verification_profile", return_value=profile):
                paths = publication.emit(ROOT, archives, core_dir, archives / "publication", "x86_64",
                                         "failure", "skipped", "c" * 40, "12345", "owner/repo",
                                         "https://github.com", "image", "6.17.0-azure", "17.11",
                                         core_resolution_path=resolution_path)
            attempt = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertEqual(attempt["profile_id"], "pg-jsonschema-publication-linux-x86_64-17.11")
            self.assertEqual(attempt["postgresql_version"], "17.11")
            self.assertEqual(attempt["core_run_id"], resolution["provenance"]["run_id"])

    def test_postgresql_15_and_16_attempts_select_resolved_core(self):
        for version, architecture in (("15.19", "arm64"), ("16.15", "x86_64")):
            with self.subTest(version=version, architecture=architecture), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archives, core_dir = root / "archives", root / "core"
                archives.mkdir()
                core_dir, resolution_path, resolution = self._core_resolution_fixture(
                    root, pg_version=version, architecture=architecture)
                profile = {"profile_revision": "b" * 64, "case_ids": list(publication.CASES)}
                with patch.object(coverage, "verification_profile", return_value=profile):
                    paths = publication.emit(ROOT, archives, core_dir, archives / "publication", architecture,
                                             "failure", "skipped", "c" * 40, "12345", "owner/repo",
                                             "https://github.com", "image", "6.17.0-azure", version,
                                             core_resolution_path=resolution_path)
                attempt = json.loads(paths[0].read_text(encoding="utf-8"))
                self.assertEqual(attempt["profile_id"], publication.profile_id(architecture, version))
                self.assertEqual(attempt["core_run_id"], resolution["provenance"]["run_id"])
                self.assertIs(attempt["release_eligible"], False)
                self.assertEqual(attempt["redistribution_status"], "postgresql-core-redistribution-review-pending")

    def test_kernel_release_must_meet_linux_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kernel_release in ("3.22.0-alpine", "not-a-kernel"):
                with self.subTest(kernel_release=kernel_release), self.assertRaises(coverage.CoverageError):
                    publication.emit(ROOT, root, root, root / "publication", "arm64", "failure", "skipped",
                                     "c" * 40, "12345", "owner/repo", "https://github.com", "image",
                                     kernel_release)

    def test_sidecar_binds_exact_archive_name_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "candidate.tar.gz"
            archive.write_bytes(b"candidate")
            digest = hashlib.sha256(b"candidate").hexdigest()
            Path(str(archive) + ".sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
            publication._sidecar(archive, digest)
            Path(str(archive) + ".sha256").write_text(f"{digest}  other.tar.gz\n", encoding="utf-8")
            with self.assertRaises(coverage.CoverageError):
                publication._sidecar(archive, digest)

    def test_emit_binds_report_to_final_archive_and_keeps_release_ineligible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = ROOT
            archives = Path(directory) / "archives"
            core_dir = Path(directory) / "core"
            output = archives / "publication"
            archives.mkdir()
            core_dir.mkdir()
            arch = "x86_64"
            archive_name = "pg_jsonschema-0.3.4-postgresql-18.6-linux-x86_64.tar.gz"
            core_name = "postgresql-18.6-linux-x86_64.tar.gz"
            archive, core = archives / archive_name, core_dir / core_name
            package_metadata = {
                "project": "pg_jsonschema", "version": "0.3.4", "sql_names": ["pg_jsonschema"],
                "requires": [], "configuration_prerequisites": [], "runtime_prerequisites": [],
                "postgresql_version": "18.6", "platform": "linux", "architecture": arch,
                "source": {"url": "https://github.com/supabase/pg_jsonschema.git",
                           "commit": publication.SOURCE_COMMIT,
                           "cargo_lock_sha256": publication.CARGO_LOCK_SHA256},
                "release_eligible": False,
                "redistribution_status": "postgresql-core-redistribution-review-pending",
            }
            cargo_inventory = {"packages": [{
                "name": "synthetic", "version": "0.1", "license": "MIT",
                "dependency_roles": ["shipped"],
                "packaged_license_notice_files": [{"path": "LICENSE", "sha256": "0" * 64}],
            }]}
            component_inventory = {"schema_version": 1, "components": [{
                "component": "pg_jsonschema", "version": "0.3.4",
                "payload_paths": ["lib/pg_jsonschema.so", "share/extension"],
                "license_file": "pg_jsonschema/LICENSE",
                "additional_license_files": ["cargo/synthetic-0.1/LICENSE"],
                "redistribution_review": {
                    "status": "resolved", "basis": "Fixture review", "source_obligation": "none",
                },
            }]}
            with tarfile.open(archive, "w:gz") as package:
                for name, contents in {
                    "pg_jsonschema/lib/pg_jsonschema.so": b"module",
                    "pg_jsonschema/share/extension/pg_jsonschema.control": b"default_version = '0.3.4'\n",
                    "pg_jsonschema/share/extension/pg_jsonschema--0.3.4.sql": b"SELECT 1;\n",
                    "pg_jsonschema/LICENSES/cargo/cargo-license-inventory.json": json.dumps(cargo_inventory).encode(),
                    "pg_jsonschema/LICENSES/pg_jsonschema-inventory.json":
                        (json.dumps(component_inventory) + "\n").encode(),
                    "pg_jsonschema/LICENSES/pg_jsonschema/LICENSE": b"Apache License\n",
                    "pg_jsonschema/LICENSES/cargo/synthetic-0.1/LICENSE": b"MIT License\n",
                    "metadata.json": (json.dumps(package_metadata) + "\n").encode(),
                }.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(contents)
                    package.addfile(member, io.BytesIO(contents))
            core_dir, resolution_path, resolution = self._core_resolution_fixture(directory)
            archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            core_hash = hashlib.sha256(core.read_bytes()).hexdigest()
            for path in (archive, core):
                Path(str(path) + ".sha256").write_text(
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n", encoding="utf-8")
            static_dir = archives / "static-analysis"
            static_dir.mkdir()
            (static_dir / "pg_jsonschema.json").write_text(json.dumps({
                    "outcome": "passed", "architecture": arch,
                "archives": [
                    {"basename": archive_name, "sha256": archive_hash},
                    {"basename": core_name, "sha256": core_hash},
                ],
            }), encoding="utf-8")
            (archives / "build-evidence.txt").write_text(
                f"pg_jsonschema_source_commit={publication.SOURCE_COMMIT}\n"
                f"cargo_lock_sha256={publication.CARGO_LOCK_SHA256}\n",
                encoding="utf-8")
            (archives / "cargo-license-inventory.json").write_text("{}\n", encoding="utf-8")
            (archives / "pg_jsonschema-component-inventory.json").write_text(
                json.dumps(component_inventory) + "\n", encoding="utf-8")
            (archives / "probe-output.txt").write_text(
                "PASS: pg_jsonschema 0.3.4 on relocated PostgreSQL 18.6 in Alpine 3.22\n", encoding="utf-8")
            profile = {"profile_revision": "b" * 64, "case_ids": list(publication.CASES)}
            with patch.object(coverage, "verification_profile", return_value=profile), \
                    patch.object(coverage, "validate_verification_record", return_value=True):
                paths = publication.emit(root, archives, core_dir, output, arch, "success", "success",
                                         "c" * 40, "12345", "owner/repo", "https://github.com",
                                         "sha256:" + "d" * 64, "6.17.0-azure",
                                         core_resolution_path=resolution_path)
            attempt = json.loads((output / "attempt.json").read_text(encoding="utf-8"))
            record = json.loads((output / "verification-record.json").read_text(encoding="utf-8"))
            self.assertEqual(paths, (output / "attempt.json", output / "current-receipt.json",
                                     output / "verification-record.json"))
            self.assertEqual(attempt["archives"][archive_name], archive_hash)
            self.assertEqual(record["assembled_core"]["sha256"], core_hash)
            self.assertEqual(record["release_eligible"], False)
            self.assertEqual(record["case_results"], {"archive-suite": "passed", "elf-closure": "passed"})
            self.assertEqual(record["environment"]["os_version"], "6.17.0")
            self.assertEqual(record["environment"]["distribution"], "Alpine Linux 3.22")
            receipt = json.loads((output / "current-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["archives"][archive_name], archive_hash)
            self.assertEqual(receipt["archives"][core_name], core_hash)
            self.assertIs(receipt["release_eligible"], False)
            self.assertEqual(receipt["redistribution_status"], "postgresql-core-redistribution-review-pending")
            temporary_root = Path(directory) / "root"
            (temporary_root / "support").mkdir(parents=True)
            (temporary_root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
            (temporary_root / "support/postgresql-releases.json").write_bytes(
                (ROOT / "support/postgresql-releases.json").read_bytes())
            with patch.object(coverage, "verification_profile", return_value=profile), \
                    patch.object(coverage, "validate_verification_record", return_value=True):
                retained = importer.import_run(temporary_root, core_dir, archives, "12345")
            self.assertTrue(any(name.endswith("/attempt.json") for name in retained))
            self.assertTrue(any(name.endswith("/verification-record.json") for name in retained))
            self.assertTrue(any(name.endswith("/pg_jsonschema-inventory.json") for name in retained))
            retained_inventory = json.loads((temporary_root
                / "support/evidence/pg_jsonschema-linux-publication-12345/18.6/x86_64"
                / "pg_jsonschema-inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(retained_inventory["components"][0]["redistribution_review"]["status"], "resolved")
            self.assertTrue((temporary_root / "support/verification/pg_jsonschema-0.3.4-postgresql-18.6-linux-x86_64-current-12345.json").is_file())
            self.assertTrue(any(name.endswith("/pg_jsonschema-0.3.4-postgresql-18.6-linux-x86_64.tar.gz.sha256")
                                for name in retained))
            attempt_path = output / "attempt.json"
            original_attempt = attempt_path.read_bytes()
            attempt = json.loads(original_attempt)
            del attempt["core_resolution"]
            attempt_path.write_text(json.dumps(attempt), encoding="utf-8")
            with patch.object(coverage, "verification_profile", return_value=profile), \
                    self.assertRaisesRegex(coverage.CoverageError, "raw attempt identity"):
                importer.import_run(temporary_root, core_dir, archives, "12345")
            attempt_path.write_bytes(original_attempt)
            resolved_path = output / "core-resolution.json"
            original_resolution = resolved_path.read_bytes()
            resolved_path.unlink()
            with patch.object(coverage, "verification_profile", return_value=profile), \
                    self.assertRaisesRegex(coverage.CoverageError, "lacks its core resolution JSON"):
                importer.import_run(temporary_root, core_dir, archives, "12345")
            resolved_path.write_bytes(original_resolution)
            original_archive = archive.read_bytes()
            archive.write_bytes(b"tampered final archive")
            with patch.object(coverage, "verification_profile", return_value=profile), \
                    patch.object(coverage, "validate_verification_record", return_value=True), \
                    self.assertRaises(coverage.CoverageError):
                importer.import_run(temporary_root, core_dir, archives, "12345")
            archive.write_bytes(original_archive)
            receipt_path = output / "current-receipt.json"
            original_receipt = receipt_path.read_bytes()
            receipt = json.loads(original_receipt)
            receipt["archives"][archive_name] = "0" * 64
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            with patch.object(coverage, "verification_profile", return_value=profile), \
                    patch.object(coverage, "validate_verification_record", return_value=True), \
                    self.assertRaises(coverage.CoverageError):
                importer.import_run(temporary_root, core_dir, archives, "12345")
            receipt_path.write_bytes(original_receipt)


if __name__ == "__main__":
    unittest.main()
