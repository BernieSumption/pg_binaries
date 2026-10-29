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
            }), encoding="utf-8")
            folder = root / "packages/postgresql"
            folder.mkdir(parents=True)
            (folder / "build.json").write_text(json.dumps({
                "sources": {"postgresql": {"project": "PostgreSQL", "url": "https://example.invalid/postgresql.tar.gz", "sha256": "a" * 64}}
            }))
            (folder / "build.sh").write_text("#!/bin/sh\n")
            runtime = root / "postgresql.tar.gz"
            development = root / "postgresql-development.tar.gz"
            runtime.write_bytes(b"runtime")
            development.write_bytes(b"development")
            manifest = root / "postgresql-build.json"
            manifest.write_text(json.dumps({"version": "18.6", "archive": {
                "filename": runtime.name, "sha256": sha256_file(runtime)}, "development_archive": {
                "filename": development.name, "sha256": sha256_file(development)}}))
            record = make_record(support, "macos-arm64", "postgresql", runtime,
                                 "0" * 40, development_archive=development)
            self.assertEqual(record["development_archive"], {
                "filename": development.name, "sha256": sha256_file(development)})
            self.assertEqual(record["postgresql_version"], "18.6")
            self.assertEqual(record["sources"][0]["id"], "postgresql")
            self.assertEqual(set(record["build_inputs"]["files"]), {"build.json", "build.sh"})
            runtime.write_bytes(b"changed after build")
            with self.assertRaisesRegex(RecordError, "does not match produced archive"):
                make_record(support, "macos-arm64", "postgresql", runtime, "0" * 40)
            with self.assertRaises(RecordError):
                make_record(support, "macos-arm64", "missing-package", runtime,
                            "0" * 40, postgresql_archive=runtime,
                            development_archive=development)

            extension = root / "packages/example"
            extension.mkdir()
            (extension / "build.json").write_text(json.dumps({
                "sources": {"example": {"project": "Example", "url": "https://example.invalid/source.tar.gz", "sha256": "b" * 64}},
                "extensions": {"example": {}}}))
            (extension / "build.sh").write_text("#!/bin/sh\n")
            (extension / "probes").mkdir()
            (extension / "probes/example.sql").write_text("SELECT 1;\n")
            output = root / "example.tar.gz"
            output.write_bytes(b"extension")
            extension_manifest = {"postgresql_version": "18.6", "archive": {
                "filename": output.name, "sha256": sha256_file(output)}, "postgresql_archive": {
                "filename": runtime.name, "sha256": "0" * 64}, "postgresql_development_archive": {
                "filename": development.name, "sha256": sha256_file(development)}}
            manifest = root / "extension-build.json"
            manifest.write_text(json.dumps(extension_manifest))
            with self.assertRaisesRegex(RecordError, "development installation used for compilation"):
                make_record(support, "macos-arm64", "example", output, "0" * 40, postgresql_archive=runtime)
            extension_manifest["postgresql_archive"]["sha256"] = sha256_file(runtime)
            manifest.write_text(json.dumps(extension_manifest))
            record = make_record(support, "macos-arm64", "example", output, "0" * 40, postgresql_archive=runtime)
            self.assertEqual(record["postgresql_development_archive"]["sha256"], sha256_file(development))


if __name__ == "__main__":
    unittest.main()
