"""Focused checks for Linux Address Standardizer candidate evidence."""

from contextlib import ExitStack
import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import coverage
from license_pointer import LicensePointerError
import emit_address_standardizer_linux_publication as publication
import import_address_standardizer_linux_publication as importer


class AddressStandardizerLinuxPublication(unittest.TestCase):
    def setUp(self):
        self.profile = {"profile_revision": "a" * 64,
                        "case_ids": ["archive-suite", "elf-closure"]}

    @staticmethod
    def write_extension_archive(path, *, include_pointer=True):
        files = {}
        if include_pointer:
            from license_pointer import LICENSE_POINTER
            files["address_standardizer/LICENSES/address_standardizer/LICENCE"] = LICENSE_POINTER.encode()
        with tarfile.open(path, "w:gz") as archive:
            for name, content in files.items():
                member = tarfile.TarInfo(name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))

    def test_profiles_are_architecture_specific_and_version_bounded(self):
        self.assertEqual(publication.profile_id("x86_64"),
                         "address-standardizer-publication-linux-x86_64-18.6")
        self.assertNotEqual(publication.profile_id("x86_64"), publication.profile_id("arm64"))
        self.assertEqual(publication.profile_id("arm64", "15.19"),
                         "address-standardizer-publication-linux-arm64-15.19")
        with self.assertRaises(coverage.CoverageError):
            publication.profile_id("aarch64")

    def test_supported_targets_come_from_profiles_and_workflow_has_no_version_gate(self):
        self.assertFalse(hasattr(publication, "CORE_PINS"))
        registry = coverage.load_json(ROOT / "support/verification-profiles.json")
        expected = {"15.19", "16.15", "17.11", "18.6"}
        self.assertEqual({profile_id.rsplit("-", 1)[1] for profile_id in registry["profiles"]
                          if profile_id.startswith("address-standardizer-publication-linux-x86_64-")}, expected)
        workflow = (ROOT / ".github/workflows/address-standardizer-linux-selected-publication.yml").read_text()
        self.assertNotIn("publication.VERSION", workflow)
        self.assertIn("--extension-version \"$ADDRESS_STANDARDIZER_VERSION\"", workflow)
        recipe = (ROOT / "scripts/address_standardizer/linux-build-in-container.sh").read_text()
        self.assertIn('Address Standardizer recipe supports 3.7.0; selected $extension_version', recipe)
        self.assertIn("license-pointer write \"$package\" address_standardizer", recipe)
        self.assertNotIn("15.19|16.15|17.11|18.6", recipe)
        self.assertNotIn("15.19|16.15|17.11|18.6",
                         (ROOT / "scripts/address_standardizer/linux-verify-in-container.sh").read_text())
        self.assertIn('"sql_names":["address_standardizer","address_standardizer_data_us"]', recipe)

    def test_selected_workflow_accepts_exact_targets_and_plans_from_support(self):
        workflow = (ROOT / ".github/workflows/address-standardizer-linux-selected-publication.yml").read_text()
        self.assertIn("tools/extension_archive_plan.py", workflow)
        self.assertIn("--project 'Address Standardizer'", workflow)
        self.assertIn("--postgresql-version \"$PG_VERSION\"", workflow)
        self.assertIn("--extension-version \"$ADDRESS_STANDARDIZER_VERSION\"", workflow)
        self.assertIn("workflow_call:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("  push:", workflow)
        self.assertIn("inputs.architecture == 'arm64' && 'ubuntu-24.04-arm'", workflow)
        self.assertIn("scripts/linux/resolve-core.sh", workflow)
        self.assertIn("core-resolution.json", workflow)
        self.assertIn("tools/import_address_standardizer_linux_publication.py", workflow)
        registry = coverage.load_json(ROOT / "support/verification-profiles.json")
        sources = registry["profiles"][publication.profile_id("x86_64")]["sources"]
        self.assertIn(".github/workflows/address-standardizer-linux-selected-publication.yml", sources)

    def test_all_publication_profiles_track_selected_workflow_and_core_build(self):
        registry = coverage.load_json(ROOT / "support/verification-profiles.json")
        workflow = ".github/workflows/address-standardizer-linux-selected-publication.yml"
        core_sources = {
            "scripts/linux/Dockerfile", "scripts/linux/build-in-container.sh",
            "scripts/linux/build.sh", "scripts/linux/resolve-core.sh",
            "tools/linux_core_pin.py", "tools/extension_archive_plan.py",
            "tools/linux_core_resolution.py",
            "tools/plan_work.py", "tools/source_archive.py",
        }
        legacy_workflows = {
            ".github/workflows/address-standardizer-linux-publication.yml",
            ".github/workflows/address-standardizer-linux-15-17-publication.yml",
        }
        targets = [profile_id for profile_id in registry["profiles"]
                   if profile_id.startswith("address-standardizer-publication-linux-")]
        for target in targets:
            with self.subTest(profile=target):
                profile = registry["profiles"][target]
                sources = set(profile["sources"])
                self.assertIn(workflow, sources)
                self.assertTrue(core_sources <= sources, core_sources - sources)
                self.assertTrue(legacy_workflows.isdisjoint(sources))
                coverage.verification_profile(ROOT, target)

    def test_case_results_preserve_failed_and_skipped_work(self):
        self.assertEqual(publication._case_results("success", "passed"),
                         {"archive-suite": "passed", "elf-closure": "passed"})
        self.assertEqual(publication._case_results("failure", "failed"),
                         {"archive-suite": "skipped", "elf-closure": "failed"})
        self.assertEqual(publication._case_results("failure", "passed"),
                         {"archive-suite": "failed", "elf-closure": "passed"})

    def test_emit_and_import_bind_candidate_to_both_archive_hashes(self):
        cases = (("18.6", "x86_64"), ("15.19", "arm64"))
        for index, (pg_version, architecture) in enumerate(cases):
            with self.subTest(postgresql_version=pg_version, architecture=architecture), \
                    tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "root"
                (root / "support").mkdir(parents=True)
                (root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
                (root / "support/postgresql-releases.json").write_bytes((ROOT / "support/postgresql-releases.json").read_bytes())
                archives, core_dir = Path(temporary) / "archives", Path(temporary) / "core"
                archives.mkdir()
                core_dir.mkdir()
                archive_name = f"address-standardizer-{publication.VERSION}-postgresql-{pg_version}-linux-{architecture}.tar.gz"
                core_name = f"postgresql-{pg_version}-linux-{architecture}.tar.gz"
                archive, core = archives / archive_name, core_dir / core_name
                self.write_extension_archive(archive)
                core.write_bytes(b"fixture core archive " + pg_version.encode())
                core_hash = hashlib.sha256(core.read_bytes()).hexdigest()
                archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
                for path, checksum in ((archive, archive_hash), (core, core_hash)):
                    Path(str(path) + ".sha256").write_text(f"{checksum}  {path.name}\n", encoding="utf-8")
                resolution = core_dir / "core-resolution.json"
                resolution.write_text("{}\n", encoding="utf-8")
                static = archives / "static-analysis"
                static.mkdir()
                (static / "address-standardizer.json").write_text(json.dumps({
                    "outcome": "passed", "architecture": architecture,
                    "archives": [{"basename": core_name, "sha256": core_hash},
                                 {"basename": archive_name, "sha256": archive_hash}],
                }), encoding="utf-8")
                (archives / "build-evidence.txt").write_text(
                    f"address_standardizer_source_commit={publication.SOURCE_COMMIT}\n"
                    f"pcre2_source_sha256={publication.PCRE2_SHA256}\n", encoding="utf-8")
                (archives / "Address-Standardizer-COPYING.txt").write_text("upstream extension licence\n", encoding="utf-8")
                (archives / "PCRE2-LICENCE.md").write_text("upstream PCRE2 licence\n", encoding="utf-8")
                (archives / "SLJIT-LICENSE.txt").write_text("upstream SLJIT licence\n", encoding="utf-8")
                (archives / "probe-output.txt").write_text(
                    f"PASS: Address Standardizer 3.7.0 with PostgreSQL {pg_version} on relocated Alpine 3.22\n",
                    encoding="utf-8")
                output = archives / "publication"
                run_id = str(12345 + index)
                args = (ROOT, archives, core_dir, output, architecture, "success", "success",
                        "c" * 40, run_id, "owner/repo", "https://github.com",
                        "sha256:" + "d" * 64, "6.17.0-azure", pg_version, resolution, "success", publication.VERSION)
                resolution_record = {"provenance": {"run_id": "99887766"}}
                with ExitStack() as stack:
                    stack.enter_context(patch.object(
                        publication, "digest",
                        side_effect=lambda path: core_hash if Path(path) == core else
                        hashlib.sha256(Path(path).read_bytes()).hexdigest()))
                    stack.enter_context(patch.object(coverage, "verification_profile", return_value=self.profile))
                    stack.enter_context(patch.object(coverage, "validate_verification_record", return_value=True))
                    stack.enter_context(patch.object(publication.linux_core_resolution,
                                                     "validate_resolution", return_value=resolution_record))
                    stack.enter_context(patch.object(importer.linux_core_resolution,
                                                     "validate_resolution", return_value=resolution_record))
                    emitted = publication.emit(*args)
                    attempt = json.loads((output / "attempt.json").read_text(encoding="utf-8"))
                    receipt = json.loads((output / "current-receipt.json").read_text(encoding="utf-8"))
                    record = json.loads((output / "verification-record.json").read_text(encoding="utf-8"))
                    data_record = json.loads((output / "verification-record-address_standardizer_data_us.json").read_text(encoding="utf-8"))
                    retained = importer.import_run(root, core_dir, archives, run_id)

                self.assertEqual(emitted, (output / "attempt.json", output / "current-receipt.json",
                                           output / "verification-record.json"))
                self.assertEqual(attempt["archives"], {archive_name: archive_hash, core_name: core_hash})
                self.assertEqual(attempt["redistribution_status"], publication.ATTEMPT_STATUS)
                self.assertEqual(attempt["profile_id"], publication.profile_id(architecture, pg_version))
                self.assertEqual(attempt["core_run_id"], "99887766")
                self.assertEqual(receipt["extension_archive"], archive_name)
                self.assertEqual(receipt["release_eligible"], False)
                self.assertEqual(receipt["redistribution_status"], publication.REDISTRIBUTION_RESOLVED)
                self.assertEqual(record["redistribution_status"], publication.REDISTRIBUTION_RESOLVED)
                self.assertEqual(record["component"], "address_standardizer")
                self.assertEqual(data_record["component"], "address_standardizer_data_us")
                self.assertEqual({**record, "component": data_record["component"]}, data_record)
                self.assertEqual(record["assembled_core"], {"archive": core_name, "sha256": core_hash,
                                                             "version": pg_version})
                self.assertEqual(record["case_results"], {"archive-suite": "passed", "elf-closure": "passed"})
                self.assertTrue(any(name.endswith("/verification-record.json") for name in retained))
                evidence = root / "support/evidence" / f"address-standardizer-linux-publication-{run_id}"
                if pg_version != "18.6":
                    evidence /= pg_version
                evidence /= architecture
                self.assertTrue((evidence / "attempt.json").is_file())
                self.assertTrue((evidence / "verification-record.json").is_file())
                self.assertTrue((evidence / "verification-record-address_standardizer_data_us.json").is_file())
                installed = root / "support/verification" / f"address-standardizer-3.7.0-postgresql-{pg_version}-linux-{architecture}-current-{run_id}.json"
                self.assertTrue(installed.is_file())
                data_installed = root / "support/verification" / f"address_standardizer_data_us-3.7.0-postgresql-{pg_version}-linux-{architecture}-current-{run_id}.json"
                self.assertTrue(data_installed.is_file())

    def test_emitter_preserves_failed_attempt_when_final_archive_lacks_license_pointer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            (root / "support").mkdir(parents=True)
            (root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
            (root / "support/postgresql-releases.json").write_bytes(
                (ROOT / "support/postgresql-releases.json").read_bytes())
            archives, core_dir = Path(temporary) / "archives", Path(temporary) / "core"
            archives.mkdir()
            core_dir.mkdir()
            archive = archives / "address-standardizer-3.7.0-postgresql-18.6-linux-x86_64.tar.gz"
            core = core_dir / "postgresql-18.6-linux-x86_64.tar.gz"
            self.write_extension_archive(archive, include_pointer=False)
            core.write_bytes(b"core")
            for path in (archive, core):
                checksum = hashlib.sha256(path.read_bytes()).hexdigest()
                Path(str(path) + ".sha256").write_text(f"{checksum}  {path.name}\n", encoding="utf-8")
            resolution = core_dir / "core-resolution.json"
            resolution.write_text("{}\n", encoding="utf-8")
            output = archives / "publication"
            args = (root, archives, core_dir, output, "x86_64", "success", "success",
                    "c" * 40, "76545", "owner/repo", "https://github.com",
                    "sha256:" + "d" * 64, "6.17.0-azure", "18.6", resolution, "success")
            with patch.object(coverage, "verification_profile", return_value=self.profile), \
                    patch.object(publication.linux_core_resolution, "validate_resolution",
                                 return_value={"provenance": {"run_id": "99887766"}}):
                with self.assertRaisesRegex(LicensePointerError, "LICENCE"):
                    publication.emit(*args)
            attempt = json.loads((output / "attempt.json").read_text(encoding="utf-8"))
            self.assertEqual(attempt["redistribution_status"], publication.ATTEMPT_STATUS)
            self.assertFalse((output / "current-receipt.json").exists())

    def test_failed_core_resolution_retains_attempt_but_cannot_publish_complete_archives(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            (root / "support").mkdir(parents=True)
            (root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
            (root / "support/postgresql-releases.json").write_bytes((ROOT / "support/postgresql-releases.json").read_bytes())
            archives, core_dir = Path(temporary) / "archives", Path(temporary) / "core"
            archives.mkdir()
            core_dir.mkdir()
            output = archives / "publication"
            args = (root, archives, core_dir, output, "x86_64", "skipped", "skipped",
                    "c" * 40, "76543", "owner/repo", "https://github.com",
                    "unavailable", "6.17.0-azure", "18.6", core_dir / "core-resolution.json", "failure")
            with patch.object(coverage, "verification_profile", return_value=self.profile):
                emitted = publication.emit(*args)
            self.assertEqual(emitted, (output / "attempt.json",))
            attempt = json.loads((output / "attempt.json").read_text(encoding="utf-8"))
            self.assertEqual(attempt["workflow_steps"], {
                "build": "skipped", "verify": "skipped", "core_resolution": "failure"})
            self.assertIsNone(attempt["core_run_id"])
            with patch.object(coverage, "verification_profile", return_value=self.profile):
                retained = importer.import_run(root, core_dir, archives, "76543")
            self.assertTrue(any(name.endswith("/attempt.json") for name in retained))

            archive = archives / "address-standardizer-3.7.0-postgresql-18.6-linux-x86_64.tar.gz"
            core = core_dir / "postgresql-18.6-linux-x86_64.tar.gz"
            archive.write_bytes(b"complete extension archive")
            core.write_bytes(b"complete core archive")
            (core_dir / "core-resolution.json").write_text("invalid provenance\n", encoding="utf-8")
            complete_args = list(args)
            complete_args[8] = "76544"
            with patch.object(coverage, "verification_profile", return_value=self.profile):
                emitted = publication.emit(*complete_args)
            self.assertEqual(emitted, (output / "attempt.json",))
            with patch.object(coverage, "verification_profile", return_value=self.profile):
                importer.import_run(root, core_dir, archives, "76544")
            self.assertFalse((output / "current-receipt.json").exists())
            self.assertFalse((output / "verification-record.json").exists())
            self.assertIn("test \"$CORE_RESOLUTION\" = success",
                          (ROOT / ".github/workflows/address-standardizer-linux-selected-publication.yml").read_text())

    def test_newly_selected_release_keeps_failure_attempt_when_recipe_has_not_been_updated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            (root / "support").mkdir()
            support = coverage.load_json(ROOT / "support.json")
            support["extensions"]["Address Standardizer"]["versions"]["3.8.0"] = {
                "postgresql_minimum_major": 15, "postgresql_maximum_major": 19,
                "operating_systems": ["macos", "linux"]}
            (root / "support.json").write_text(json.dumps(support), encoding="utf-8")
            (root / "support/postgresql-releases.json").write_bytes((ROOT / "support/postgresql-releases.json").read_bytes())
            archives, core = Path(temporary) / "archives", Path(temporary) / "core"
            archives.mkdir()
            core.mkdir()
            output = archives / "publication"
            resolution = core / "core-resolution.json"
            resolution.write_text("{}\n", encoding="utf-8")
            with patch.object(coverage, "verification_profile", return_value=self.profile), \
                    patch.object(publication.linux_core_resolution, "validate_resolution",
                                  return_value={"provenance": {"run_id": "123"}}):
                emitted = publication.emit(root, archives, core, output, "x86_64", "failure", "skipped",
                    "c" * 40, "87654", "owner/repo", "https://github.com", "unavailable",
                    "6.17.0-azure", "18.6", resolution, "success", "3.8.0")
            attempt = json.loads((output / "attempt.json").read_text(encoding="utf-8"))
            self.assertEqual(emitted, (output / "attempt.json",))
            self.assertEqual(attempt["version"], "3.8.0")
            self.assertEqual(attempt["workflow_steps"]["build"], "failure")

    def test_import_rejects_attempt_without_core_resolution_outcome(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "support").mkdir()
            (root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
            (root / "support/postgresql-releases.json").write_bytes((ROOT / "support/postgresql-releases.json").read_bytes())
            archives, core = root / "archives", root / "core"
            archives.mkdir()
            core.mkdir()
            (archives / "publication").mkdir()
            attempt = {"schema_version": 1, "run_id": "567", "source_revision": "c" * 40,
                       "profile_id": publication.profile_id("arm64"), "postgresql_version": "18.6",
                       "version": publication.VERSION, "architecture": "arm64", "core_run_id": None,
                       "steps": {"archive-suite": "skipped", "elf-closure": "skipped"},
                       "workflow_steps": {"build": "failure", "verify": "skipped"},
                       "release_eligible": False, "redistribution_status": publication.BLOCK,
                       "archives_present": {"postgresql-18.6-linux-arm64.tar.gz": True,
                                            "address-standardizer-3.7.0-postgresql-18.6-linux-arm64.tar.gz": False},
                       "reports": {}}
            (archives / "publication/attempt.json").write_text(json.dumps(attempt), encoding="utf-8")
            with patch.object(coverage, "verification_profile", return_value=self.profile), \
                    self.assertRaises(coverage.CoverageError):
                importer.import_run(root, core, archives, "567")


if __name__ == "__main__":
    unittest.main()
