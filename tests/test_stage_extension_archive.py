import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "stage_extension_archive", Path(__file__).resolve().parents[1] / "tools" / "stage_extension_archive.py")
staging = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(staging)


class StageExtensionArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archives = self.root / "archives"
        self.archives.mkdir()
        self.staging = self.root / "staging"
        self.support = {"extensions": {"Example Project": {
            "sql_names": ["example"], "versions": {"2.0": {}, "2.1": {}}}}}
        self.inventory = {"schema_version": 1, "extensions": {"example": {}}}
        self.downloads = {}
        for version, member_name in (("2.0", "lib/old.so"), ("2.1", "lib/new.so")):
            archive_name = f"example-{version}-linux-x86_64.tar.gz"
            archive_path = self.archives / archive_name
            self.write_archive(archive_path, version, member_name)
            digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            self.downloads[version] = {
                "postgresql_support": {"from": "15.10", "to": "15.10"},
                "url": f"https://example.test/{archive_name}", "sha256": digest,
            }
        self.inventory["extensions"]["example"] = {
            version: {"downloads": {"linux-x86_64": [download]}}
            for version, download in self.downloads.items()
        }
        self.inventory_path = self.root / "inventory.json"
        self.support_path = self.root / "support.json"
        self.inventory_path.write_text(json.dumps(self.inventory), encoding="utf-8")
        self.support_path.write_text(json.dumps(self.support), encoding="utf-8")

    def write_archive(self, path, version, file_name, legacy_nested_licenses=False):
        metadata = ("{\"project\":\"example_project\","
                    f"\"version\":\"{version}\",\"platform\":\"linux\","
                    "\"architecture\":\"x86_64\",\"sql_names\":[\"example\"],"
                    "\"requires\":[],\"configuration_prerequisites\":[],"
                    "\"runtime_prerequisites\":[]}").encode()
        with tarfile.open(path, "w:gz") as archive:
            self.add_file(archive, "example_project/" + file_name, b"module")
            license_root = "example_project/LICENSES"
            if legacy_nested_licenses:
                license_root += "/example_project"
            inventory_name = "inventory.json" if legacy_nested_licenses else "example_project-inventory.json"
            self.add_file(archive, license_root + "/" + inventory_name, b'{"schema_version":1,"components":[{}]}')
            self.add_file(archive, license_root + "/COPYING", b"licence text")
            self.add_file(archive, "metadata.json", metadata)

    @staticmethod
    def add_file(archive, name, contents):
        member = tarfile.TarInfo(name)
        member.size = len(contents)
        member.mode = 0o755
        archive.addfile(member, io.BytesIO(contents))

    def stage(self, version, prefix):
        return staging.select_and_stage(
            self.inventory, self.support, "15.10", "linux-x86_64",
            "Example Project", version, "example", self.archives, prefix, self.staging)

    def run_cli(self, version, prefix):
        script = Path(__file__).resolve().parents[1] / "tools" / "stage_extension_archive.py"
        return subprocess.run(
            [sys.executable, str(script), "--inventory", str(self.inventory_path),
             "--support", str(self.support_path), "--postgresql-version", "15.10",
             "--platform", "linux-x86_64", "--project", "Example Project",
             "--extension-version", version, "--sql-name", "example",
             "--archive-directory", str(self.archives), "--prefix", str(prefix),
             "--staging-root", str(self.staging)],
            capture_output=True, text=True, check=False)

    def test_cli_selects_both_versions_and_rejects_checksum_mismatch(self):
        old_prefix = self.root / "cli-old-prefix"
        new_prefix = self.root / "cli-new-prefix"
        old_result = self.run_cli("2.0", old_prefix)
        new_result = self.run_cli("2.1", new_prefix)
        self.assertEqual(old_result.returncode, 0, old_result.stderr)
        self.assertEqual(new_result.returncode, 0, new_result.stderr)
        self.assertTrue((old_prefix / "lib/old.so").is_file())
        self.assertFalse((old_prefix / "lib/new.so").exists())
        self.assertTrue((new_prefix / "lib/new.so").is_file())
        self.assertFalse((new_prefix / "lib/old.so").exists())

        archive = self.archives / "example-2.0-linux-x86_64.tar.gz"
        archive.write_bytes(archive.read_bytes() + b"changed")
        rejected = self.run_cli("2.0", self.root / "rejected-prefix")
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("checksum mismatch", rejected.stderr)
        self.assertFalse((self.root / "rejected-prefix").exists())

    def test_cli_keeps_merge_payload_mode(self):
        payload = self.root / "payload"
        (payload / "share").mkdir(parents=True)
        (payload / "share/example.control").write_text("control", encoding="utf-8")
        prefix = self.root / "merged-prefix"
        script = Path(__file__).resolve().parents[1] / "tools" / "stage_extension_archive.py"
        result = subprocess.run(
            [sys.executable, str(script), "--merge-payload", str(payload),
             "--prefix", str(prefix)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((prefix / "share/example.control").read_text(encoding="utf-8"), "control")

    def test_selects_exact_core_archive_and_stages_only_its_version(self):
        old_prefix = self.root / "old-prefix"
        new_prefix = self.root / "new-prefix"
        selected = self.stage("2.0", old_prefix)
        self.stage("2.1", new_prefix)
        self.assertEqual(selected["url"], self.downloads["2.0"]["url"])
        self.assertTrue((old_prefix / "lib/old.so").is_file())
        self.assertTrue((old_prefix / "LICENSES/example_project-inventory.json").is_file())
        self.assertEqual((old_prefix / "LICENSES/COPYING").read_bytes(), b"licence text")
        self.assertFalse((old_prefix / "lib/new.so").exists())
        self.assertTrue((new_prefix / "lib/new.so").is_file())
        self.assertFalse((new_prefix / "lib/old.so").exists())
        old_stage = self.staging / (
            f"Example Project-2.0-{self.downloads['2.0']['sha256'][:12]}")
        new_stage = self.staging / (
            f"Example Project-2.1-{self.downloads['2.1']['sha256'][:12]}")
        self.assertTrue((old_stage / "example_project/lib/old.so").is_file())
        self.assertFalse((old_stage / "example_project/lib/new.so").exists())
        self.assertTrue((new_stage / "example_project/lib/new.so").is_file())
        self.assertFalse((new_stage / "example_project/lib/old.so").exists())

    def test_rejects_legacy_nested_inventory_without_rewriting_payload(self):
        archive_path = self.archives / "example-2.0-linux-x86_64.tar.gz"
        self.write_archive(archive_path, "2.0", "lib/old.so", legacy_nested_licenses=True)
        download = self.downloads["2.0"]
        download["sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        prefix = self.root / "prefix"
        with self.assertRaisesRegex(staging.StagingError, "example_project-inventory.json"):
            self.stage("2.0", prefix)
        self.assertFalse(prefix.exists())

    def test_preserves_core_license_inventory_when_staging_extension(self):
        prefix = self.root / "prefix"
        (prefix / "LICENSES").mkdir(parents=True)
        (prefix / "LICENSES/inventory.json").write_text("core inventory")
        self.stage("2.0", prefix)
        self.assertEqual((prefix / "LICENSES/inventory.json").read_text(), "core inventory")
        self.assertTrue((prefix / "LICENSES/example_project-inventory.json").is_file())

    def test_rejects_missing_extension_license_inventory(self):
        archive_path = self.archives / "example-2.0-linux-x86_64.tar.gz"
        self.write_archive(archive_path, "2.0", "lib/old.so")
        # Keep only the module and metadata in this archive.
        with tarfile.open(archive_path, "w:gz") as archive:
            self.add_file(archive, "example_project/lib/old.so", b"module")
            self.add_file(archive, "metadata.json", b'{"project":"example_project","version":"2.0","platform":"linux","architecture":"x86_64","sql_names":["example"],"requires":[],"configuration_prerequisites":[],"runtime_prerequisites":[]}')
        self.downloads["2.0"]["sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(staging.StagingError, "LICENSES/example_project-inventory.json"):
            self.stage("2.0", self.root / "prefix")

    def test_rejects_archive_whose_inventory_range_excludes_selected_core(self):
        self.inventory["extensions"]["example"]["2.0"]["downloads"]["linux-x86_64"][0][
            "postgresql_support"] = {"from": "16.0", "to": "16.5"}
        with self.assertRaisesRegex(staging.SelectionError, "no archive covering"):
            self.stage("2.0", self.root / "prefix")

    def test_rejects_checksum_mismatch_before_staging(self):
        archive_path = self.archives / "example-2.0-linux-x86_64.tar.gz"
        archive_path.write_bytes(archive_path.read_bytes() + b"changed")
        with self.assertRaisesRegex(staging.StagingError, "checksum mismatch"):
            self.stage("2.0", self.root / "prefix")

    def test_collision_rejects_file_and_directory_type_conflicts(self):
        payload = self.root / "payload"
        (payload / "share").mkdir(parents=True)
        (payload / "share/a-new.control").write_text("new", encoding="utf-8")
        (payload / "share/control.control").write_text("new", encoding="utf-8")
        prefix = self.root / "prefix"
        (prefix / "share").mkdir(parents=True)
        (prefix / "share/control.control").write_text("old", encoding="utf-8")
        with self.assertRaisesRegex(staging.StagingError, "payload collision"):
            staging.merge_payload(payload, prefix)
        self.assertEqual((prefix / "share/control.control").read_text(encoding="utf-8"), "old")
        self.assertFalse((prefix / "share/a-new.control").exists())

    def test_checked_extraction_accepts_internal_library_link_and_rejects_escape(self):
        archive_path = self.root / "core.tar.gz"
        destination = self.root / "checked-core"
        with tarfile.open(archive_path, "w:gz") as archive:
            self.add_file(archive, "postgresql/lib/libpq.5.dylib", b"library")
            link = tarfile.TarInfo("postgresql/lib/libpq.dylib")
            link.type = tarfile.SYMTYPE
            link.linkname = "libpq.5.dylib"
            archive.addfile(link)
        staging._extract_checked(archive_path, destination)
        self.assertEqual((destination / "postgresql/lib/libpq.dylib").read_bytes(), b"library")

        with tarfile.open(archive_path, "w:gz") as archive:
            link = tarfile.TarInfo("postgresql/lib/libpq.dylib")
            link.type = tarfile.SYMTYPE
            link.linkname = "../../../outside"
            archive.addfile(link)
        with self.assertRaisesRegex(staging.StagingError, "archive link escapes"):
            staging._extract_checked(archive_path, self.root / "rejected-core")


if __name__ == "__main__":
    unittest.main()
