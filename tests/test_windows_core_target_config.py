import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import windows_core_target_config as config
from windows_core_pin import load_identity


class WindowsCoreTargetConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.version = "17.11"
        self.run_id = "123456"
        self.attempt = "3"
        self.revision = "a" * 40
        self.base = ROOT / f"support/windows-core-pins/{self.version}-x86_64.json"
        self.archive = self.root / f"postgresql-{self.version}-windows-x86_64.tar.gz"

    def tearDown(self):
        self.temp.cleanup()

    def make_archive(self, *, manifest_override=None):
        manifest = {
            "component": "postgresql", "version": self.version,
            "postgresql_version": self.version, "platform": "windows",
            "architecture": "x86_64",
            "build_id": f"github-{self.run_id}-{self.attempt}",
            "source_revision": self.revision,
        }
        manifest.update(manifest_override or {})
        import io
        body = json.dumps(manifest).encode()
        with tarfile.open(self.archive, "w:gz") as tar:
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        Path(str(self.archive) + ".sha256").write_text(
            f"{digest}  {self.archive.name}\n", encoding="ascii")

    def test_generates_identity_and_loader_accepts_explicit_path(self):
        self.make_archive()
        output = self.root / "generated.json"
        result = config.create_target(self.base, self.archive, self.run_id, output, self.attempt)
        self.assertEqual(result["run_id"], self.run_id)
        self.assertEqual(result["build_id"], f"github-{self.run_id}-{self.attempt}")
        self.assertEqual(result["source_revision"], self.revision)
        self.assertEqual(result["sha256"], hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertEqual(result["artifact_name"], f"windows-postgresql-{self.version}-pilot")
        self.assertEqual(load_identity(output, pg_version=self.version), result)

    def test_rejects_forged_sidecar_manifest_and_mismatched_attempt(self):
        self.make_archive()
        sidecar = Path(str(self.archive) + ".sha256")
        sidecar.write_text("0" * 64 + "\n", encoding="ascii")
        with self.assertRaisesRegex(ValueError, "checksum"):
            config.create_target(self.base, self.archive, self.run_id, self.root / "out.json", self.attempt)

        self.make_archive(manifest_override={"source_revision": "z" * 40})
        with self.assertRaisesRegex(ValueError, "manifest"):
            config.create_target(self.base, self.archive, self.run_id, self.root / "out.json", self.attempt)

        self.make_archive()
        with self.assertRaisesRegex(ValueError, "manifest"):
            config.create_target(self.base, self.archive, self.run_id, self.root / "out.json", "2")
        with self.assertRaisesRegex(ValueError, "attempt"):
            config.create_target(self.base, self.archive, self.run_id, self.root / "out.json", "03")


if __name__ == "__main__":
    unittest.main()
