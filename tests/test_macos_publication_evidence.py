"""Tests for shared macOS publication evidence primitives."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import coverage
import macos_publication_evidence as evidence


class MacOSPublicationEvidenceTests(unittest.TestCase):
    def test_sidecar_binds_archive_name_and_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "postgresql.tar.gz"
            archive.write_bytes(b"archive bytes")
            digest = evidence.sha256_file(archive)
            sidecar = archive.with_name(archive.name + ".sha256")
            sidecar.write_text(f"{digest.upper()} *{archive.name}\n", encoding="utf-8")

            evidence.check_sidecar(archive, digest, "missing sidecar for {name}")
            sidecar.write_text(f"{'0' * 64}  {archive.name}\n", encoding="utf-8")
            with self.assertRaisesRegex(coverage.CoverageError, "checksum sidecar does not match"):
                evidence.check_sidecar(archive, digest, "missing sidecar for {name}")

    def test_json_reader_rejects_oversized_and_non_object_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            oversized = Path(directory) / "large.json"
            oversized.write_text('{"x": 1}', encoding="utf-8")
            with self.assertRaisesRegex(coverage.CoverageError, "at most 2 bytes"):
                evidence.read_json_object(oversized, max_bytes=2)

            non_object = Path(directory) / "array.json"
            non_object.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(coverage.CoverageError, "expected JSON object"):
                evidence.read_json_object(non_object)

    def test_retention_rejects_conflicting_bytes_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, destination = base / "source.json", base / "evidence" / "source.json"
            source.write_text('{"run": 1}\n', encoding="utf-8")
            destination.parent.mkdir()
            destination.write_text('{"run": 2}\n', encoding="utf-8")
            copies = []

            with self.assertRaisesRegex(coverage.CoverageError, "refusing to replace retained evidence"):
                evidence.retain(source, destination, copies)
            with self.assertRaisesRegex(coverage.CoverageError, "refusing to replace retained evidence"):
                evidence.copy_retained([(source, destination)])
            self.assertEqual(destination.read_text(encoding="utf-8"), '{"run": 2}\n')

    def test_batch_rejects_conflicting_sources_for_one_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first, second, destination = base / "first", base / "second", base / "kept"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            with self.assertRaisesRegex(coverage.CoverageError, "refusing to replace retained evidence"):
                evidence.copy_retained([(first, destination), (second, destination)])
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
