"""Focused checks for macOS Address Standardizer publication records."""

import hashlib
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import coverage
from license_pointer import LICENSE_POINTER
import emit_address_standardizer_macos_publication as emitter
import import_address_standardizer_macos_publication as importer


class AddressStandardizerMacOSPublication(unittest.TestCase):
    def test_emitter_writes_one_archive_bound_record_per_sql_name_and_importer_retains_both(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            root = work / "root"
            (root / "support").mkdir(parents=True)
            (root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
            (root / "support/postgresql-releases.json").write_bytes(
                (ROOT / "support/postgresql-releases.json").read_bytes())
            core_dir, archive_dir = work / "core", work / "archives"
            core_dir.mkdir()
            archive_dir.mkdir()
            pg, arch, platform, run_id = "18.6", "arm64", "macos-arm64", "123456"
            core_name = f"postgresql-{pg}-{platform}.tar.gz"
            ext_name = f"address-standardizer-3.7.0-postgresql-{pg}-{platform}.tar.gz"
            core, extension = core_dir / core_name, archive_dir / ext_name
            core.write_bytes(b"core archive")
            core_hash = hashlib.sha256(core.read_bytes()).hexdigest()
            metadata = {"project": "Address Standardizer", "version": "3.7.0",
                        "sql_names": ["address_standardizer", "address_standardizer_data_us"],
                        "postgresql_version": pg, "platform": "macos", "architecture": arch,
                        "core_archive": {"basename": core_name, "sha256": core_hash}}
            with tarfile.open(extension, "w:gz") as archive:
                data = json.dumps(metadata).encode()
                member = tarfile.TarInfo("metadata.json")
                member.size = len(data)
                import io
                archive.addfile(member, io.BytesIO(data))
                pointer = tarfile.TarInfo("address_standardizer/LICENSES/address_standardizer/LICENCE")
                pointer.size = len(LICENSE_POINTER.encode())
                archive.addfile(pointer, io.BytesIO(LICENSE_POINTER.encode()))
            target = work / "target.json"
            target.write_text(json.dumps({"postgresql_version": pg, "architecture": arch,
                                          "platform": platform,
                                          "profile_id": f"address-standardizer-publication-macos-{arch}-{pg}"}))
            for path in (core, extension):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                Path(str(path) + ".sha256").write_text(f"{digest}  {path.name}\n")
            attempt_dir = archive_dir / "publication"
            attempt_dir.mkdir(parents=True)
            extension_hash = hashlib.sha256(extension.read_bytes()).hexdigest()
            attempt = {"schema_version": 1, "run_id": run_id, "source_revision": "c" * 40,
                       "profile_id": f"address-standardizer-publication-macos-{arch}-{pg}",
                       "postgresql_version": pg, "version": "3.7.0", "architecture": arch,
                       "steps": {"archive-suite": "success", "macho-closure": "success"},
                       "release_eligible": False,
                       "redistribution_status": emitter.ATTEMPT_STATUS,
                       "archives_present": {core_name: True, ext_name: True},
                       "archives": {core_name: core_hash, ext_name: extension_hash}}
            (attempt_dir / "attempt.json").write_text(json.dumps(attempt))
            (archive_dir / "probe-output.txt").write_text("probe passed\n")
            (archive_dir / "static-analysis.json").write_text(json.dumps(
                {"archives": {core_name: core_hash, ext_name: extension_hash},
                 "passed": True, "findings": []}))
            env = {"GITHUB_SHA": "c" * 40, "GITHUB_RUN_ID": run_id,
                   "GITHUB_REPOSITORY": "owner/repo", "GITHUB_SERVER_URL": "https://github.com"}
            profile = {"profile_id": attempt["profile_id"], "profile_revision": "a" * 64,
                       "case_ids": ["archive-suite", "macho-closure"], "scope": "publication",
                       "platforms": [platform]}
            with patch.dict(os.environ, env), \
                    patch.object(emitter.extension_archive_plan, "select_target"), \
                    patch.object(coverage, "verification_profile", return_value=profile), \
                    patch.object(coverage, "validate_verification_record"):
                emitter.emit(root, core_dir, archive_dir, archive_dir, target,
                             {"archive-suite": "success", "macho-closure": "success"},
                             "15.0", "sha256:" + "d" * 64)
            primary = json.loads((attempt_dir / "verification-record.json").read_text())
            data_us = json.loads((attempt_dir / "verification-record-address_standardizer_data_us.json").read_text())
            self.assertEqual(primary["component"], "address_standardizer")
            self.assertEqual(data_us, {**primary, "component": "address_standardizer_data_us"})

            with patch.object(importer.extension_archive_plan, "select_target"), \
                    patch.object(coverage, "verification_profile", return_value=profile), \
                    patch.object(coverage, "validate_verification_record"):
                retained = importer.import_run(root, core_dir, archive_dir, run_id, target)
            self.assertTrue(any(path.endswith("address-standardizer-3.7.0-postgresql-18.6-macos-arm64-current-123456.json")
                                for path in retained))
            self.assertTrue((root / "support/verification/address_standardizer_data_us-3.7.0-postgresql-18.6-macos-arm64-current-123456.json").is_file())


if __name__ == "__main__":
    unittest.main()
