"""Focused checks for Linux Address Standardizer candidate evidence."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import coverage
import emit_address_standardizer_linux_publication as publication
import import_address_standardizer_linux_publication as importer


class AddressStandardizerLinuxPublication(unittest.TestCase):
    def setUp(self):
        self.profile = {"profile_revision": "a" * 64,
                        "case_ids": ["archive-suite", "elf-closure"]}

    def test_profiles_are_architecture_specific_and_version_bounded(self):
        self.assertEqual(publication.profile_id("x86_64"),
                         "address-standardizer-publication-linux-x86_64-18.6")
        self.assertNotEqual(publication.profile_id("x86_64"), publication.profile_id("arm64"))
        self.assertEqual(publication.profile_id("arm64", "15.19"),
                         "address-standardizer-publication-linux-arm64-15.19")
        with self.assertRaises(coverage.CoverageError):
            publication.profile_id("aarch64")

    def test_core_pins_cover_selected_postgresql_releases_and_architectures(self):
        self.assertEqual(set(publication.CORE_PINS), {"15.19", "16.15", "17.11", "18.6"})
        self.assertEqual({version: set(pins[1]) for version, pins in publication.CORE_PINS.items()},
                         {version: {"x86_64", "arm64"} for version in publication.CORE_PINS})

    def test_matrix_workflow_plans_targets_before_matrix_expansion(self):
        workflow = (ROOT / ".github/workflows/address-standardizer-linux-15-17-publication.yml").read_text()
        publish = workflow.split("\n  publish:\n", 1)[1]
        publish_header = publish.split("\n    steps:\n", 1)[0]
        self.assertIn("matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}", publish_header)
        self.assertNotIn("matrix.", publish_header.split("\n    strategy:", 1)[0])
        self.assertIn("if: needs.plan.outputs.has_targets == 'true'", publish_header)
        self.assertIn('os.environ["EVENT_NAME"] == "workflow_dispatch"', workflow)

    def test_case_results_preserve_failed_and_skipped_work(self):
        self.assertEqual(publication._case_results("success", "passed"),
                         {"archive-suite": "passed", "elf-closure": "passed"})
        self.assertEqual(publication._case_results("failure", "failed"),
                         {"archive-suite": "skipped", "elf-closure": "failed"})
        self.assertEqual(publication._case_results("failure", "passed"),
                         {"archive-suite": "failed", "elf-closure": "passed"})

    def test_core_artifact_download_preserves_its_pilot_subdirectory(self):
        workflow = (ROOT / ".github/workflows/address-standardizer-linux-publication.yml").read_text()
        self.assertEqual(workflow.count("path: ${{ runner.temp }}/core\n"), 2)
        self.assertEqual(workflow.count('"$RUNNER_TEMP/core/pilot"'), 8)

    def test_emit_and_import_bind_candidate_to_both_archive_hashes(self):
        cases = (("18.6", "x86_64", "39081368117",
                  "f89a7047812324b85c3b0bb29a3118fc55a492b17956f1fe0d74d1788d33d680"),
                 ("15.19", "arm64", "39082151857",
                  "9b570ba3827c2255a668375ec09ffe8d249e473d8389a7191e7c1fd77fbdca97"))
        for index, (pg_version, architecture, expected_core_run, core_hash) in enumerate(cases):
            with self.subTest(postgresql_version=pg_version, architecture=architecture), \
                    tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "root"
                (root / "support").mkdir(parents=True)
                (root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
                archives, core_dir = Path(temporary) / "archives", Path(temporary) / "core"
                archives.mkdir()
                core_dir.mkdir()
                archive_name = f"address-standardizer-{publication.VERSION}-postgresql-{pg_version}-linux-{architecture}.tar.gz"
                core_name = f"postgresql-{pg_version}-linux-{architecture}.tar.gz"
                archive, core = archives / archive_name, core_dir / core_name
                archive.write_bytes(b"candidate archive containing both SQL extensions")
                core.write_bytes(b"fixture core archive " + pg_version.encode())
                archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
                for path, checksum in ((archive, archive_hash), (core, core_hash)):
                    Path(str(path) + ".sha256").write_text(f"{checksum}  {path.name}\n", encoding="utf-8")
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
                (archives / "PCRE2-COPYING.txt").write_text("upstream PCRE2 licence\n", encoding="utf-8")
                (archives / "probe-output.txt").write_text(
                    f"PASS: Address Standardizer 3.7.0 with PostgreSQL {pg_version} on relocated Alpine 3.22\n",
                    encoding="utf-8")
                output = archives / "publication"
                run_id = str(12345 + index)
                args = (ROOT, archives, core_dir, output, architecture, "success", "success",
                        "c" * 40, run_id, "owner/repo", "https://github.com",
                        "sha256:" + "d" * 64, "6.17.0-azure", pg_version)
                with patch.object(publication, "digest",
                                  side_effect=lambda path: core_hash if Path(path) == core else
                                  hashlib.sha256(Path(path).read_bytes()).hexdigest()), \
                        patch.object(coverage, "verification_profile", return_value=self.profile), \
                        patch.object(coverage, "validate_verification_record", return_value=True):
                    emitted = publication.emit(*args)
                    attempt = json.loads((output / "attempt.json").read_text(encoding="utf-8"))
                    receipt = json.loads((output / "current-receipt.json").read_text(encoding="utf-8"))
                    record = json.loads((output / "verification-record.json").read_text(encoding="utf-8"))
                    retained = importer.import_run(root, core_dir, archives, run_id)

                self.assertEqual(emitted, (output / "attempt.json", output / "current-receipt.json",
                                           output / "verification-record.json"))
                self.assertEqual(attempt["archives"], {archive_name: archive_hash, core_name: core_hash})
                self.assertEqual(attempt["profile_id"], publication.profile_id(architecture, pg_version))
                self.assertEqual(attempt["core_run_id"], expected_core_run)
                self.assertEqual(core_hash, publication.CORE_PINS[pg_version][1][architecture])
                self.assertEqual(receipt["extension_archive"], archive_name)
                self.assertEqual(receipt["release_eligible"], False)
                self.assertEqual(receipt["redistribution_status"], publication.BLOCK)
                self.assertEqual(record["component"], "address_standardizer")
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
                installed = root / "support/verification" / f"address-standardizer-3.7.0-postgresql-{pg_version}-linux-{architecture}-current-{run_id}.json"
                self.assertTrue(installed.is_file())

    def test_import_rejects_core_bytes_that_differ_from_pinned_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "support").mkdir()
            (root / "support.json").write_bytes((ROOT / "support.json").read_bytes())
            archives, core = root / "archives", root / "core"
            archives.mkdir()
            core.mkdir()
            (archives / "publication").mkdir()
            attempt = {"schema_version": 1, "run_id": "567", "source_revision": "c" * 40,
                       "profile_id": publication.profile_id("arm64"), "postgresql_version": "18.6",
                       "version": publication.VERSION, "architecture": "arm64", "core_run_id": publication.CORE_PINS["18.6"][0],
                       "steps": {"archive-suite": "skipped", "elf-closure": "skipped"},
                       "workflow_steps": {"build": "failure", "verify": "skipped"},
                       "release_eligible": False, "redistribution_status": publication.BLOCK,
                       "archives_present": {"postgresql-18.6-linux-arm64.tar.gz": True,
                                            "address-standardizer-3.7.0-postgresql-18.6-linux-arm64.tar.gz": False},
                       "reports": {}}
            (archives / "publication/attempt.json").write_text(json.dumps(attempt), encoding="utf-8")
            (core / "postgresql-18.6-linux-arm64.tar.gz").write_bytes(b"wrong core bytes")
            (core / "postgresql-18.6-linux-arm64.tar.gz.sha256").write_text(
                hashlib.sha256(b"wrong core bytes").hexdigest() + "  postgresql-18.6-linux-arm64.tar.gz\n",
                encoding="utf-8")
            archive_name = "address-standardizer-3.7.0-postgresql-18.6-linux-arm64.tar.gz"
            (archives / archive_name).write_bytes(b"candidate")
            attempt["archives_present"][archive_name] = True
            (archives / "publication/attempt.json").write_text(json.dumps(attempt), encoding="utf-8")
            with patch.object(coverage, "verification_profile", return_value=self.profile), \
                    patch.object(publication, "CORE_PINS", {"18.6": (publication.CORE_PINS["18.6"][0], {"arm64": "0" * 64})}), \
                    self.assertRaises(coverage.CoverageError):
                importer.import_run(root, core, archives, "567")


if __name__ == "__main__":
    unittest.main()
