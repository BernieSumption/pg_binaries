import hashlib
import json
from pathlib import Path
import sys
import tempfile
import tarfile
import io
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import coverage
import emit_tiger_macos_publication as emitter
import import_tiger_macos_publication as importer

ROOT = Path(__file__).resolve().parents[1]


class TigerMacOSPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.core = self.base / "core"
        self.postgis = self.base / "postgis"
        self.tiger = self.base / "tiger"
        self.verification = self.base / "verification"
        self.verification.mkdir()
        self.output = self.verification / "publication"
        for directory in (self.core, self.postgis, self.tiger):
            directory.mkdir()
        self.pg, self.arch = "18.6", "arm64"
        self.names = {
            "core": f"postgresql-{self.pg}-macos-{self.arch}.tar.gz",
            "postgis": f"postgis-3.6.4-postgresql-{self.pg}-macos-{self.arch}.tar.gz",
            "tiger": f"postgis_tiger_geocoder-2025.2-postgresql-{self.pg}-macos-{self.arch}.tar.gz",
        }
        self.digests = {}
        core_archive = self.core / self.names["core"]
        core_archive.write_bytes(b"core archive bytes")
        self.digests[core_archive.name] = hashlib.sha256(core_archive.read_bytes()).hexdigest()
        common = {"postgresql_version": self.pg, "platform": "macos", "architecture": self.arch}
        metadata = {
            "postgis": {**common, "project": "postgis", "version": "3.6.4",
                        "core_archive": {"basename": core_archive.name,
                                         "sha256": self.digests[core_archive.name]}},
            "tiger": {**common, "project": "postgis_tiger_geocoder", "version": "2025.2",
                      "requires": ["PostGIS"],
                      "source": {"url": "https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-2025.2.tar.gz",
                                 "sha256": "c33cfbfb40785db8754a36be66060e8d023773e7e1be8fb8a622bb3c48db9f54"}},
        }
        for key, directory in (("postgis", self.postgis), ("tiger", self.tiger)):
            archive = directory / self.names[key]
            data = json.dumps(metadata[key]).encode()
            member = tarfile.TarInfo("metadata.json")
            member.size = len(data)
            with tarfile.open(archive, "w:gz") as stream:
                stream.addfile(member, io.BytesIO(data))
        for key, directory in (("core", self.core), ("postgis", self.postgis), ("tiger", self.tiger)):
            archive = directory / self.names[key]
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.digests[archive.name] = digest
            archive.with_name(archive.name + ".sha256").write_text(f"{digest}  {archive.name}\n")
        (self.verification / "probe-output.txt").write_text(
            "CREATE EXTENSION\nCREATE EXTENSION\nCREATE EXTENSION\nSET\nDO\n")
        report = {"passed": True, "architecture": self.arch,
                  "archives": [{"basename": name, "sha256": digest}
                               for name, digest in self.digests.items()]}
        (self.verification / "static-analysis.json").write_text(json.dumps(report))
        self.env = {"GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "12345",
                    "GITHUB_REPOSITORY": "example/pg_binaries",
                    "GITHUB_SERVER_URL": "https://github.com"}

    def tearDown(self):
        self.temp.cleanup()

    def emit(self):
        return emitter.emit(ROOT, self.core, self.postgis, self.tiger, self.output,
                            self.pg, self.arch, "success", "success", "15.0",
                            "macos-15-arm64", self.env)

    def test_record_binds_all_three_archives_and_the_prerequisite(self):
        self.emit()
        record = json.loads((self.output / "verification-record.json").read_text())
        self.assertEqual(record["outcome"], "passed")
        self.assertEqual(record["sha256"], self.digests[self.names["tiger"]])
        self.assertEqual(record["assembled_core"]["sha256"], self.digests[self.names["core"]])
        self.assertEqual(record["prerequisite_archives"][0]["sha256"],
                         self.digests[self.names["postgis"]])
        self.assertEqual(record["test_cases"], ["archive-suite", "static-analysis"])

    def test_static_analysis_must_bind_final_archive_bytes(self):
        path = self.verification / "static-analysis.json"
        path.write_text(json.dumps({"passed": True, "architecture": self.arch, "archives": {}}))
        with self.assertRaisesRegex(coverage.CoverageError, "not bound"):
            self.emit()

    def test_sidecar_mismatch_is_rejected(self):
        archive = self.postgis / self.names["postgis"]
        archive.with_name(archive.name + ".sha256").write_text("0" * 64 + "  " + archive.name + "\n")
        with self.assertRaisesRegex(coverage.CoverageError, "sidecar"):
            self.emit()

    def test_import_retains_only_compact_reports_and_verification_record(self):
        self.emit()
        artifact = self.base / "artifact"
        for name in ("core", "output", "verification/postgis", "verification/publication"):
            (artifact / name).mkdir(parents=True, exist_ok=True)
        import shutil
        for key, source in (("core", self.core), ("postgis", self.postgis), ("tiger", self.tiger)):
            destination = {"core": artifact / "core", "postgis": artifact / "verification/postgis",
                          "tiger": artifact / "output"}[key]
            for archive in source.iterdir():
                if archive.name.startswith(self.names[key]):
                    shutil.copyfile(archive, destination / archive.name)
        shutil.copyfile(self.verification / "probe-output.txt", artifact / "verification/probe-output.txt")
        shutil.copyfile(self.verification / "static-analysis.json", artifact / "verification/static-analysis.json")
        for filename in ("verification-record.json", "archive-hashes.json"):
            shutil.copyfile(self.output / filename, artifact / "verification/publication" / filename)
        retained = self.base / "retained"
        files = importer.import_run(ROOT, artifact, "12345", self.pg, self.arch, retained)
        self.assertEqual(len(files), 4)
        self.assertTrue((retained / "support/evidence/tiger-macos-publication-12345/arm64/18.6/probe-output.txt").is_file())
        record = retained / "support/verification/postgis_tiger_geocoder-2025.2-postgresql-18.6-macos-arm64-current-12345.json"
        self.assertEqual(json.loads(record.read_text())["sha256"], self.digests[self.names["tiger"]])
        self.assertFalse((retained / "core" / self.names["core"]).exists())


if __name__ == "__main__":
    unittest.main()
