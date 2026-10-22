import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from publication_preflight import _archive_license_pointer
from license_pointer import LICENSE_POINTER


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


if __name__ == "__main__":
    unittest.main()
