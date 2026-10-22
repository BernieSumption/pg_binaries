import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "stage_first_release", Path(__file__).resolve().parents[1] / "tools" / "stage_first_release.py")
stage_first_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage_first_release)


class StageFirstReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source = self.root / "tests" / "profile.py"
        source.parent.mkdir(parents=True)
        source.write_text("current publication cases\n", encoding="utf-8")
        self.platforms = sorted(["linux-x86_64", "linux-arm64", "macos-x86_64", "macos-arm64",
                                 "windows-x86_64"])
        profile = {"schema_version": 1, "profiles": {"test-publication": {
            "scope": "publication", "platforms": self.platforms,
            "case_ids": ["archive-suite"], "sources": ["tests/profile.py"]}}}
        profile_path = self.root / "support" / "verification-profiles.json"
        profile_path.parent.mkdir()
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        self.support = {
            "schema_version": 1, "version_selection_as_of": "2026-10-17",
            "postgresql": {"minimum_major": 15},
            "os_support": {os_name: {"minimum_version": "1"}
                           for os_name in ("linux", "macos", "windows")},
            "architectures": ["x86_64", "arm64"],
            "platform_architectures": {"linux": ["x86_64", "arm64"],
                                        "macos": ["x86_64", "arm64"],
                                        "windows": ["x86_64"]},
            "extensions": {"Example": {
                "sql_names": ["example", "example_extra"],
                "versions": {"1.0": {"postgresql_minimum_major": 15}}}},
        }
        self.snapshot = {
            "as_of": "2026-01-01", "source": "https://example.test/releases",
            "support_status": {"source": "https://example.test/support", "as_of": "2026-01-01",
                               "supported_majors": [15]},
            "releases": [{"version": "15.10", "release_date": "2025-10-01"}],
        }
        self.archive_dir = self.root / "archives"
        self.archive_dir.mkdir()
        self.record_dir = self.root / "records"
        self.record_dir.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def _record(self, component, version, pg_version, checksum, platform, core_checksum=None):
        profile = stage_first_release._coverage.verification_profile(self.root, "test-publication")
        os_name, architecture = platform.split("-", 1)
        record = {
            "schema_version": 2, "scope": "publication", "profile_id": "test-publication",
            "profile_revision": profile["profile_revision"], "outcome": "passed",
            "sha256": checksum, "component": component, "version": version,
            "platform": platform, "postgresql_version": pg_version,
            "test_revision": "a" * 40, "test_cases": profile["case_ids"],
            "case_results": {"archive-suite": "passed"},
            "environment": {"os": os_name, "architecture": architecture, "os_version": "1",
                             "clean_system": True, "endpoint": "current", "image_id": "test",
                             "dependency_check_profile": "fixture-v1",
                             "dependency_checks_passed": True},
        }
        if component != "postgresql":
            record["assembled_core"] = {
                "archive": f"postgresql-{pg_version}-{platform}.tar.gz",
                "version": pg_version, "sha256": core_checksum or "c" * 64,
            }
        return record

    def _write_record(self, name, record):
        path = self.record_dir / f"{name}.json"
        path.write_text(json.dumps(record), encoding="utf-8")

    def _core(self, platform, version="15.10"):
        os_name, architecture = platform.split("-", 1)
        path = self.archive_dir / f"postgresql-{version}-{platform}.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, data in {
                "postgresql/share/extension/plpgsql.control": b"comment = 'builtin'\n",
                "postgresql/manifest.json": json.dumps({
                    "schema_version": 1, "component": "postgresql", "version": version,
                    "postgresql_version": version, "platform": os_name, "architecture": architecture,
                    "included_extensions": ["plpgsql"],
                }).encode(),
            }.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        return path

    def test_groups_sql_names_when_extension_filenames_sort_before_core(self):
        archives = []
        for platform in self.platforms:
            core = self._core(platform)
            extension = self.archive_dir / f"example-1.0-postgresql-15.10-{platform}.tar.gz"
            extension.write_bytes(f"staged extension bytes for {platform}".encode())
            archives.extend([core, extension])
            core_sha = hashlib.sha256(core.read_bytes()).hexdigest()
            ext_sha = hashlib.sha256(extension.read_bytes()).hexdigest()
            self._write_record(f"core-{platform}", self._record("postgresql", "15.10", "15.10", core_sha, platform))
            for sql_name in ("example", "example_extra"):
                self._write_record(f"{sql_name}-{platform}", self._record(
                    sql_name, "1.0", "15.10", ext_sha, platform, core_sha))

        duplicate_dir = self.archive_dir / "duplicate-copy"
        duplicate_dir.mkdir()
        duplicate = duplicate_dir / extension.name
        shutil.copyfile(extension, duplicate)
        archives.append(duplicate)
        archives.sort(key=lambda path: path.name)

        proposals, staged, missing = stage_first_release.prepare_manifests(
            archives, [self.record_dir], self.support, self.snapshot,
            "catalog-20261022-1", root=self.root)

        self.assertEqual(missing, [])
        extension_proposal = next(item for item in proposals if item["component"] == "Example")
        self.assertEqual(extension_proposal["postgresql_support"], {"from": "15.10", "to": "15.10"})
        self.assertEqual({record["component"] for record in extension_proposal["verification"]},
                         {"example", "example_extra"})
        self.assertEqual(len(staged), len(self.platforms) * 2)
        for asset in staged.values():
            self.assertEqual(hashlib.sha256(Path(asset["path"]).read_bytes()).hexdigest(), asset["sha256"])

    def test_staging_accepts_repacked_windows_postgis_15_evidence_under_current_profile(self):
        repository = Path(__file__).resolve().parents[1]
        platform = "windows-x86_64"
        pg_version = "15.19"
        core = self.archive_dir / f"postgresql-{pg_version}-{platform}.tar.gz"
        included = ["plpgsql"]
        manifest = {
            "schema_version": 1, "component": "postgresql", "version": pg_version,
            "postgresql_version": pg_version, "platform": "windows", "architecture": "x86_64",
            "included_extensions": included,
        }
        with tarfile.open(core, "w:gz") as archive:
            for name, data in {
                "postgresql/share/extension/plpgsql.control": b"comment = 'builtin'\n",
                "postgresql/manifest.json": json.dumps(manifest).encode(),
            }.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        postgis = self.archive_dir / f"postgis-3.6.4-postgresql-{pg_version}-{platform}.tar.gz"
        postgis.write_bytes(b"staged metadata-repacked PostGIS bytes")
        core_sha = hashlib.sha256(core.read_bytes()).hexdigest()
        postgis_sha = hashlib.sha256(postgis.read_bytes()).hexdigest()

        core_record = json.loads((repository / "support/verification/postgresql-15.19-windows-x86_64-current-39695202767.json").read_text())
        core_record["sha256"] = core_sha
        self._write_record("core-windows", core_record)
        postgis_components = ("postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology")
        for component in postgis_components:
            record_path = repository / (
                f"support/verification/postgis-3.6.4-postgresql-{pg_version}-windows-x86_64-"
                f"{component}-current-metadata-repack-20261022.json")
            record = json.loads(record_path.read_text())
            record["sha256"] = postgis_sha
            record["assembled_core"]["sha256"] = core_sha
            self._write_record(component, record)

        support = stage_first_release._coverage.load_json(repository / "support.json")
        snapshot = stage_first_release._coverage.load_json(repository / "support/postgresql-releases.json")
        proposals, _staged, _missing = stage_first_release.prepare_manifests(
            [core, postgis], [self.record_dir], support, snapshot,
            "catalog-20261022-1", root=repository)

        self.assertTrue(any(item["component"] == "PostGIS" for item in proposals), _missing)
        proposal = next(item for item in proposals if item["component"] == "PostGIS")
        self.assertEqual(proposal["sha256"], postgis_sha)
        self.assertEqual({record["component"] for record in proposal["verification"]}, set(postgis_components))

    def test_sha_mismatch_reports_the_selected_extension_target(self):
        archives = []
        for platform in self.platforms:
            core = self._core(platform)
            extension = self.archive_dir / f"example-1.0-postgresql-15.10-{platform}.tar.gz"
            extension.write_bytes(f"staged extension bytes for {platform}".encode())
            archives.extend([core, extension])
            core_sha = hashlib.sha256(core.read_bytes()).hexdigest()
            self._write_record(f"core-{platform}", self._record("postgresql", "15.10", "15.10", core_sha, platform))
            for sql_name in ("example", "example_extra"):
                self._write_record(f"{sql_name}-{platform}", self._record(
                    sql_name, "1.0", "15.10", "0" * 64, platform, core_sha))

        proposals, staged, missing = stage_first_release.prepare_manifests(
            archives, [self.record_dir], self.support, self.snapshot,
            "catalog-20261022-1", root=self.root)

        self.assertFalse(any(item["component"] == "Example" for item in proposals))
        self.assertEqual(len(staged), len(self.platforms))
        self.assertTrue(any("extension example 1.0 PostgreSQL 15.10 linux-x86_64" in item
                            for item in missing))

    def test_core_sha_mismatch_does_not_cover_the_selected_extension_target(self):
        archives = []
        for platform in self.platforms:
            core = self._core(platform)
            extension = self.archive_dir / f"example-1.0-postgresql-15.10-{platform}.tar.gz"
            extension.write_bytes(f"staged extension bytes for {platform}".encode())
            archives.extend([core, extension])
            core_sha = hashlib.sha256(core.read_bytes()).hexdigest()
            ext_sha = hashlib.sha256(extension.read_bytes()).hexdigest()
            self._write_record(f"core-{platform}", self._record("postgresql", "15.10", "15.10", core_sha, platform))
            for sql_name in ("example", "example_extra"):
                self._write_record(f"{sql_name}-{platform}", self._record(
                    sql_name, "1.0", "15.10", ext_sha, platform, "d" * 64))

        proposals, staged, missing = stage_first_release.prepare_manifests(
            archives, [self.record_dir], self.support, self.snapshot,
            "catalog-20261022-1", root=self.root)

        self.assertFalse(any(item["component"] == "Example" for item in proposals))
        self.assertEqual(len(staged), len(self.platforms))
        self.assertTrue(any("extension example 1.0 PostgreSQL 15.10 linux-x86_64" in item
                            and "lacks matching current-profile SHA evidence" in item
                            for item in missing))

    def test_prerequisite_sha_must_match_the_selected_staged_archive(self):
        self.support["extensions"]["Prerequisite"] = {
            "sql_names": ["prerequisite"], "requires": [],
            "versions": {"1.0": {"postgresql_minimum_major": 15}},
        }
        self.support["extensions"]["Example"]["requires"] = ["Prerequisite"]
        self.support["extensions"]["Example"]["requires_versions"] = {
            "Prerequisite": {"minimum_version": "1.0"},
        }
        archives = []
        bad_records = []
        good_records = []
        for platform in self.platforms:
            core = self._core(platform)
            prerequisite = self.archive_dir / f"prerequisite-1.0-postgresql-15.10-{platform}.tar.gz"
            prerequisite.write_bytes(f"prerequisite bytes for {platform}".encode())
            extension = self.archive_dir / f"example-1.0-postgresql-15.10-{platform}.tar.gz"
            extension.write_bytes(f"extension bytes for {platform}".encode())
            archives.extend([core, prerequisite, extension])

            core_sha = hashlib.sha256(core.read_bytes()).hexdigest()
            prerequisite_sha = hashlib.sha256(prerequisite.read_bytes()).hexdigest()
            extension_sha = hashlib.sha256(extension.read_bytes()).hexdigest()
            self._write_record(f"core-{platform}", self._record(
                "postgresql", "15.10", "15.10", core_sha, platform))
            self._write_record(f"prerequisite-{platform}", self._record(
                "prerequisite", "1.0", "15.10", prerequisite_sha, platform, core_sha))
            prereq_ref = {"project": "Prerequisite", "archive": prerequisite.name,
                          "version": "1.0", "sha256": prerequisite_sha}
            for sql_name in ("example", "example_extra"):
                bad = self._record(sql_name, "1.0", "15.10", extension_sha, platform, core_sha)
                bad["prerequisite_archives"] = [{**prereq_ref, "sha256": "0" * 64}]
                bad_records.append((f"{sql_name}-{platform}", bad))
                good = {**bad, "prerequisite_archives": [prereq_ref]}
                good_records.append((f"{sql_name}-{platform}", good))

        for name, record in bad_records:
            self._write_record(name, record)
        proposals, _staged, _missing = stage_first_release.prepare_manifests(
            archives, [self.record_dir], self.support, self.snapshot,
            "catalog-20261022-1", root=self.root)
        self.assertFalse(any(item["component"] == "Example" for item in proposals))

        for name, record in good_records:
            self._write_record(name, record)
        proposals, _staged, _missing = stage_first_release.prepare_manifests(
            archives, [self.record_dir], self.support, self.snapshot,
            "catalog-20261022-1", root=self.root)
        self.assertTrue(any(item["component"] == "Example" for item in proposals))

    def test_exact_build_filename_limits_the_postgresql_targets_it_can_serve(self):
        self.snapshot["support_status"]["supported_majors"].append(16)
        self.snapshot["releases"].append({"version": "16.6", "release_date": "2025-10-01"})
        archives = []
        for platform in self.platforms:
            core_checksums = {}
            for pg_version in ("15.10", "16.6"):
                core = self._core(platform, pg_version)
                archives.append(core)
                core_sha = hashlib.sha256(core.read_bytes()).hexdigest()
                core_checksums[pg_version] = core_sha
                self._write_record(f"core-{platform}-{pg_version}", self._record(
                    "postgresql", pg_version, pg_version, core_sha, platform))
            extension = self.archive_dir / f"example-1.0-postgresql-15.10-{platform}.tar.gz"
            extension.write_bytes(b"one archive with matching evidence for two cores")
            archives.append(extension)
            ext_sha = hashlib.sha256(extension.read_bytes()).hexdigest()
            for pg_version in ("15.10", "16.6"):
                for sql_name in ("example", "example_extra"):
                    self._write_record(f"{sql_name}-{platform}-{pg_version}", self._record(
                        sql_name, "1.0", pg_version, ext_sha, platform, core_checksums[pg_version]))

        proposals, _staged, missing = stage_first_release.prepare_manifests(
            archives, [self.record_dir], self.support, self.snapshot,
            "catalog-20261022-1", root=self.root)

        extension_proposals = [item for item in proposals if item["component"] == "Example"]
        self.assertEqual(len(extension_proposals), len(self.platforms))
        self.assertTrue(all(item["postgresql_support"] == {"from": "15.10", "to": "15.10"}
                            for item in extension_proposals))
        self.assertTrue(all({record["postgresql_version"] for record in item["verification"]} == {"15.10"}
                            for item in extension_proposals))
        self.assertTrue(any("extension example 1.0 PostgreSQL 16.6" in item
                            and "no staged archive" in item for item in missing))


if __name__ == "__main__":
    unittest.main()
