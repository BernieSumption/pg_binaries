import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "pg_cron"))
from macos_target import SOURCE_SHA256, SOURCE_URL, load_target


class PgCronMacosTargetTests(unittest.TestCase):
    def setUp(self):
        self.target = self.target_for("18.6")

    def target_for(self, version):
        return {
            "schema_version": 1,
            "profile_id": f"pgcron-publication-macos-arm64-{version}",
            "postgresql_version": version,
            "pg_cron_version": "1.6.8",
            "architecture": "arm64",
            "platform": "macos-arm64",
            "source": {"url": SOURCE_URL, "sha256": SOURCE_SHA256},
            "core_archive": {
                "basename": f"postgresql-{version}-macos-arm64.tar.gz",
                "run_id": "39123456789",
                "sha256": "a" * 64,
                "build_id": "github-39123456789-2",
                "source_revision": "b" * 40,
            },
        }

    def load(self, target):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target.json"
            path.write_text(json.dumps(target))
            return load_target(path)

    def test_checked_core_identity_drives_archive_name(self):
        values = self.load(self.target)
        self.assertEqual(values["core_build_id"], "github-39123456789-2")
        self.assertEqual(values["extension_basename"],
                         "pg_cron-1.6.8-postgresql-18.6-macos-arm64.tar.gz")

    def test_accepts_each_postgresql_release_selected_for_macos(self):
        for version in ("15.19", "16.15", "17.11", "18.6"):
            with self.subTest(version=version):
                values = self.load(self.target_for(version))
                self.assertEqual(values["postgresql_version"], version)
                self.assertEqual(values["core_basename"],
                                 f"postgresql-{version}-macos-arm64.tar.gz")
                self.assertEqual(values["extension_basename"],
                                 f"pg_cron-1.6.8-postgresql-{version}-macos-arm64.tar.gz")

    def test_rejects_postgresql_release_not_in_selected_target_matrix(self):
        with self.assertRaisesRegex(ValueError, "not selected for pg_cron macOS"):
            self.load(self.target_for("14.22"))

    def test_accepts_unpinned_base_target(self):
        target = json.loads(json.dumps(self.target))
        target["core_archive"] = {"basename": target["core_archive"]["basename"]}
        values = self.load(target)
        self.assertFalse(values["resolved"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target.json"
            path.write_text(json.dumps(target))
            with self.assertRaisesRegex(ValueError, "has not been resolved"):
                load_target(path, require_resolved=True)

    def test_rejects_core_hash_that_does_not_match_sha256_format(self):
        target = json.loads(json.dumps(self.target))
        target["core_archive"]["sha256"] = "not-a-digest"
        with self.assertRaisesRegex(ValueError, "core archive identity"):
            self.load(target)

    def test_rejects_source_identity_change(self):
        target = json.loads(json.dumps(self.target))
        target["source"]["sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "source identity"):
            self.load(target)

    def test_rejects_run_id_and_build_id_disagreement(self):
        target = json.loads(json.dumps(self.target))
        target["core_archive"]["build_id"] = "github-39123456788-2"
        with self.assertRaisesRegex(ValueError, "core archive identity"):
            self.load(target)


if __name__ == "__main__":
    unittest.main()
