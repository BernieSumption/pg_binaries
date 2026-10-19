import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import macos_core_target_config as config


class MacosCoreTargetConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.revision = "a" * 40
        self.run_id = "123456"

    def tearDown(self):
        self.temp.cleanup()

    def base(self, project):
        version = "17.11"
        platform = "macos-arm64"
        target = {
            "schema_version": 1, "profile_id": f"{project}-publication-macos-arm64-{version}",
            "postgresql_version": version, "architecture": "arm64", "platform": platform,
            "core_archive": {"basename": f"postgresql-{version}-{platform}.tar.gz",
                             "run_id": "old", "sha256": "b" * 64,
                             "build_id": "github-old-1", "source_revision": "c" * 40},
            "source": {"url": f"https://example.test/{project}.tar.gz", "sha256": "d" * 64},
        }
        if project == "pgtap":
            target["pgtap_version"] = "1.3.4"
        path = self.root / f"{project}.json"
        path.write_text(json.dumps(target), encoding="utf-8")
        return path, target

    def archive(self, target, *, attempt="1", manifest_override=None, duplicate=False, unsafe=False, symlink=False):
        name = target["core_archive"]["basename"]
        path = self.root / name
        manifest = {
            "component": "postgresql", "version": target["postgresql_version"],
            "postgresql_version": target["postgresql_version"], "platform": "macos",
            "architecture": target["architecture"], "build_id": f"github-{self.run_id}-{attempt}",
            "source_revision": self.revision,
        }
        manifest.update(manifest_override or {})
        with tarfile.open(path, "w:gz") as tar:
            import io
            body = json.dumps(manifest).encode()
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
            if duplicate:
                tar.addfile(info, io.BytesIO(body))
            if symlink:
                link = tarfile.TarInfo("postgresql/bin/link")
                link.type = tarfile.SYMTYPE
                link.linkname = "target"
                tar.addfile(link)
            if unsafe:
                bad = tarfile.TarInfo("postgresql/../escape")
                bad.size = 0
                tar.addfile(bad, io.BytesIO(b""))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        Path(str(path) + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="ascii")
        return path

    def test_preserves_hypopg_fields_and_replaces_core_identity(self):
        base_path, original = self.base("hypopg")
        archive = self.archive(original)
        output = self.root / "out.json"
        result = config.create_target(base_path, archive, self.run_id, output)
        self.assertEqual({k: v for k, v in result.items() if k != "core_archive"},
                         {k: v for k, v in original.items() if k != "core_archive"})
        self.assertEqual(result["core_archive"], {
            "basename": archive.name, "run_id": self.run_id,
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "build_id": f"github-{self.run_id}-1", "source_revision": self.revision})
        self.assertEqual(json.loads(output.read_text()), result)

    def test_accepts_stable_base_without_run_provenance(self):
        base_path, original = self.base("hypopg")
        original["core_archive"] = {
            "basename": original["core_archive"]["basename"],
            "sha256": "b" * 64,
        }
        base_path.write_text(json.dumps(original), encoding="utf-8")
        archive = self.archive(original)
        result = config.create_target(base_path, archive, self.run_id, self.root / "out.json")
        self.assertEqual(result["core_archive"]["run_id"], self.run_id)
        self.assertEqual(result["core_archive"]["source_revision"], self.revision)

    def test_accepts_base_with_only_core_basename(self):
        base_path, original = self.base("pg_cron")
        original["core_archive"] = {"basename": original["core_archive"]["basename"]}
        base_path.write_text(json.dumps(original), encoding="utf-8")
        archive = self.archive(original)
        result = config.create_target(base_path, archive, self.run_id, self.root / "out.json")
        self.assertEqual(result["core_archive"]["sha256"],
                         hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(result["core_archive"]["build_id"], f"github-{self.run_id}-1")

    def test_accepts_positive_rerun_attempt(self):
        base_path, original = self.base("hypopg")
        archive = self.archive(original, attempt="3")
        result = config.create_target(base_path, archive, self.run_id, self.root / "out.json", "3")
        self.assertEqual(result["core_archive"]["build_id"], f"github-{self.run_id}-3")

    def test_preserves_pgtap_fields(self):
        base_path, original = self.base("pgtap")
        archive = self.archive(original)
        result = config.create_target(base_path, archive, self.run_id, self.root / "out.json")
        self.assertEqual(result["pgtap_version"], original["pgtap_version"])
        self.assertEqual(result["source"], original["source"])
        self.assertEqual(result["core_archive"]["run_id"], self.run_id)

    def test_rejects_archive_name_mismatch(self):
        base_path, original = self.base("hypopg")
        archive = self.archive(original)
        wrong_name = self.root / "other.tar.gz"
        wrong_name.write_bytes(archive.read_bytes())
        Path(str(wrong_name) + ".sha256").write_text(Path(str(archive) + ".sha256").read_text())
        with self.assertRaisesRegex(ValueError, "name"):
            config.create_target(base_path, wrong_name, self.run_id, self.root / "out.json")

    def test_rejects_bad_hash_manifest_and_source_identity(self):
        base_path, original = self.base("pgtap")
        archive = self.archive(original)
        Path(str(archive) + ".sha256").write_text("0" * 64 + "\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            config.create_target(base_path, archive, self.run_id, self.root / "out.json")
        archive = self.archive(original, manifest_override={"build_id": "github-9-1"})
        with self.assertRaisesRegex(ValueError, "manifest"):
            config.create_target(base_path, archive, self.run_id, self.root / "out.json")
        archive = self.archive(original)
        with self.assertRaisesRegex(ValueError, "run ID"):
            config.create_target(base_path, archive, "12x", self.root / "out.json")
        with self.assertRaisesRegex(ValueError, "attempt"):
            config.create_target(base_path, archive, self.run_id, self.root / "out.json", "0")

    def test_allows_archive_symlinks_without_extracting_them(self):
        base_path, original = self.base("hypopg")
        archive = self.archive(original, symlink=True)
        config.create_target(base_path, archive, self.run_id, self.root / "out.json")

    def test_rejects_duplicate_or_unsafe_tar_entries(self):
        base_path, original = self.base("hypopg")
        for kwargs in ({"duplicate": True}, {"unsafe": True}):
            archive = self.archive(original, **kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                config.create_target(base_path, archive, self.run_id, self.root / "out.json")


if __name__ == "__main__":
    unittest.main()
