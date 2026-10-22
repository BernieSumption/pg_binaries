import io
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
        self.assertIn("Join-Path $extensionExtract 'metadata.json'", verifier)

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
