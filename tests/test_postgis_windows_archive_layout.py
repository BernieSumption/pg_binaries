import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import coverage
from publication_preflight import _archive_license_pointer
from license_pointer import LICENSE_POINTER
import emit_postgis_windows_publication as emitter


class PostgisWindowsArchiveLayoutTests(unittest.TestCase):
    def test_builder_places_metadata_beside_payload_and_verifier_reads_it(self):
        builder = (REPO / "scripts/postgis/windows-build.sh").read_text()
        verifier = (REPO / "scripts/postgis/windows-verify-publication.ps1").read_text()
        self.assertIn('python - "$output_root/package/metadata.json"', builder)
        self.assertIn('tar -czf "$archive" -C "$output_root/package" postgis metadata.json', builder)
        self.assertIn("'configuration_prerequisites': [], 'runtime_prerequisites': []", builder)
        self.assertIn("Join-Path $extensionExtract 'metadata.json'", verifier)
        self.assertIn("$metadata.configuration_prerequisites -isnot [array]", verifier)
        self.assertIn("$metadata.runtime_prerequisites -isnot [array]", verifier)

    def test_publication_emitter_requires_explicit_empty_prerequisite_arrays(self):
        metadata = {
            "project": "PostGIS", "version": "3.6.4", "postgresql_version": "18.6",
            "platform": "windows", "architecture": "x86_64",
            "sql_names": emitter.SQL_NAMES, "requires": [],
            "configuration_prerequisites": [], "runtime_prerequisites": [],
            "core_archive": {"basename": "postgresql-18.6-windows-x86_64.tar.gz", "sha256": "a" * 64},
            "release_eligible": False,
        }
        emitter.validate_archive_metadata(metadata, "18.6", "postgresql-18.6-windows-x86_64.tar.gz", "a" * 64)
        del metadata["runtime_prerequisites"]
        with self.assertRaisesRegex(coverage.CoverageError, "does not bind this selected core"):
            emitter.validate_archive_metadata(metadata, "18.6", "postgresql-18.6-windows-x86_64.tar.gz", "a" * 64)

    def test_reverified_postgis_profiles_include_the_tiger_workflow_source(self):
        tiger_workflow = ".github/workflows/tiger-windows-selected-publication.yml"
        registry = coverage.load_json(REPO / "support/verification-profiles.json")["profiles"]
        for pg_version in ("16.15", "17.11", "18.6"):
            profile_id = f"postgis-publication-windows-x86_64-{pg_version}"
            profile = coverage.verification_profile(REPO, profile_id)
            self.assertIn(tiger_workflow, registry[profile_id]["sources"])
            repack_record = next((REPO / "support/verification").glob(
                f"postgis-3.6.4-postgresql-{pg_version}-windows-x86_64-postgis-current-metadata-repack-*.json"))
            old = json.loads(repack_record.read_text())
            self.assertNotEqual(profile["profile_revision"], old["profile_revision"])
        self.assertNotIn(tiger_workflow, registry["postgis-publication-windows-x86_64-15.19"]["sources"])

    def test_archive_has_only_payload_and_sibling_metadata_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "postgis.tar.gz"
            members = {
                "postgis/LICENSES/postgis/LICENCE": LICENSE_POINTER.encode(),
                "metadata.json": b'{"project":"PostGIS"}',
            }
            with tarfile.open(archive_path, "w:gz") as archive:
                for name, payload in members.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
            _archive_license_pointer(archive_path, "postgis", metadata_sibling=True)

    def test_publication_emitter_reads_sibling_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "postgis.tar.gz"
            contents = b'{"project":"PostGIS"}'
            with tarfile.open(archive_path, "w:gz") as archive:
                member = tarfile.TarInfo("metadata.json")
                member.size = len(contents)
                archive.addfile(member, io.BytesIO(contents))
            self.assertEqual(emitter.archive_metadata(archive_path), {"project": "PostGIS"})

    def test_publication_emitter_rejects_nested_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "postgis.tar.gz"
            contents = b'{"project":"PostGIS"}'
            with tarfile.open(archive_path, "w:gz") as archive:
                member = tarfile.TarInfo("postgis/metadata.json")
                member.size = len(contents)
                archive.addfile(member, io.BytesIO(contents))
            with self.assertRaisesRegex(coverage.CoverageError, "requires one bounded metadata.json"):
                emitter.archive_metadata(archive_path)


if __name__ == "__main__":
    unittest.main()
