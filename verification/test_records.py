import json
from pathlib import Path
import tempfile
import unittest

from verification.records import RecordError, make_record, sha256_file


class BuildRecordTests(unittest.TestCase):
    def test_postgresql_records_development_archive_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            support = root / "support.json"
            support.write_text(json.dumps({
                "targets": {"macos-arm64": {}},
                "postgresql": {"source": {"url": "https://example.invalid/postgresql.tar.gz",
                                          "sha256": "a" * 64}},
            }), encoding="utf-8")
            runtime = root / "postgresql.tar.gz"
            development = root / "postgresql-development.tar.gz"
            runtime.write_bytes(b"runtime")
            development.write_bytes(b"development")
            record = make_record(support, "macos-arm64", "postgresql", runtime,
                                 "0" * 40, development_archive=development)
            self.assertEqual(record["development_archive"], {
                "filename": development.name, "sha256": sha256_file(development)})
            with self.assertRaises(RecordError):
                make_record(support, "macos-arm64", "missing-package", runtime,
                            "0" * 40, postgresql_archive=runtime,
                            development_archive=development)


if __name__ == "__main__":
    unittest.main()
