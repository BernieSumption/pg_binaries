import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import source_archive
import windows_core_candidate as candidate


class WindowsCoreCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.version = "17.11"
        self.revision = "a" * 40
        self.run_id = "123456"
        self.attempt = 2
        self.base = ROOT / f"support/windows-core-pins/{self.version}-x86_64.json"
        self.archive = self.output / f"postgresql-{self.version}-windows-x86_64.tar.gz"
        src = source_archive.source_archive("postgresql", self.version, "tar.gz", ROOT)
        manifest = {
            "component": "postgresql", "version": self.version,
            "postgresql_version": self.version, "platform": "windows", "architecture": "x86_64",
            "build_id": f"github-{self.run_id}-{self.attempt}", "source_revision": self.revision,
            "source_archive": src, "source_sha256": src["sha256"],
        }
        body = json.dumps(manifest).encode()
        with tarfile.open(self.archive, "w:gz") as tar:
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        Path(str(self.archive) + ".sha256").write_text(f"{digest}  {self.archive.name}\n", encoding="ascii")
        self.row = {"path": str(self.archive), "source": {
            "run_id": self.run_id, "run_attempt": self.attempt,
            "head_sha": self.revision, "artifact_name": f"windows-postgresql-{self.version}-pilot",
        }}
        self.manifest = manifest

    def tearDown(self):
        self.temp.cleanup()

    def resolve(self):
        return candidate.resolve(base_pin=self.base, output_directory=self.output / "out",
            repository="owner/repo", branch="spike", current_run_id="999")

    def discovery_result(self, _manifest_path, archives):
        def fake(**kwargs):
            Path(kwargs["manifest_path"]).write_text(json.dumps({"archives": archives}), encoding="utf-8")
            return []
        return fake

    def selected_manifest(self, configuration=None):
        manifest = dict(self.manifest)
        if configuration is not None:
            manifest["build_configuration"] = configuration
        body = json.dumps(manifest).encode()
        with tarfile.open(self.archive, "w:gz") as tar:
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        Path(str(self.archive) + ".sha256").write_text(f"{digest}  {self.archive.name}\n", encoding="ascii")

    def test_selected_candidate_is_preferred_and_provenance_is_recorded(self):
        self.selected_manifest(
            "postgresql-17.11;builder=windows-runner;meson=debugoptimized;"
            "postgresql=icu,lz4,zstd,zlib,openssl,libxml,libxslt,no-uuid,no-readline;"
            "compiler=MSVC;vcpkg=revision;runtime=vcpkg-and-msvc-dlls")
        row = {"path": str(self.archive), "source": {
            **self.row["source"], "artifact_name": f"windows-core-selected-{self.version}-build-{self.run_id}"}}
        calls = []

        def discover(**kwargs):
            calls.append(kwargs["workflow"])
            Path(kwargs["manifest_path"]).write_text(json.dumps({"archives": [row]}), encoding="utf-8")
            return []

        with patch.object(candidate.discovery, "discover", side_effect=discover), \
             patch.object(candidate, "_relevant_inputs_match", return_value=True):
            result = candidate.resolve(base_pin=self.base, output_directory=self.output / "out",
                repository="owner/repo", branch="spike", current_run_id="999", selected_core=True)
        self.assertEqual(calls, [Path(candidate.SELECTED_WORKFLOW).name])
        self.assertEqual(result["candidate_kind"], "selected")
        target = json.loads(Path(result["target"]).read_text())
        self.assertEqual(target["artifact_name"], row["source"]["artifact_name"])

    def test_stale_selected_candidate_falls_back_to_pilot(self):
        calls = []

        def discover(**kwargs):
            calls.append(kwargs["workflow"])
            row = dict(self.row)
            row["source"] = dict(self.row["source"])
            if kwargs["workflow"] == Path(candidate.SELECTED_WORKFLOW).name:
                row["source"]["artifact_name"] = f"windows-core-selected-{self.version}-build-{self.run_id}"
            else:
                row["source"]["artifact_name"] = f"windows-postgresql-{self.version}-pilot"
            Path(kwargs["manifest_path"]).write_text(json.dumps({"archives": [row]}), encoding="utf-8")
            return []

        with patch.object(candidate.discovery, "discover", side_effect=discover), \
             patch.object(candidate, "_relevant_inputs_match", return_value=True):
            result = candidate.resolve(base_pin=self.base, output_directory=self.output / "out",
                repository="owner/repo", branch="spike", current_run_id="999", selected_core=True)
        self.assertEqual(calls, [Path(candidate.SELECTED_WORKFLOW).name, "windows-pilot.yml"])
        self.assertEqual(result["status"], "checked")
        self.assertEqual(result["candidate_kind"], "pilot")

    def test_selected_candidate_recipe_must_be_core_only(self):
        self.selected_manifest("postgresql-17.11;builder=windows-runner;pgvector-0.8.7;compiler=MSVC")
        row = {"path": str(self.archive), "source": {
            **self.row["source"], "artifact_name": f"windows-core-selected-{self.version}-build-{self.run_id}"}}
        with patch.object(candidate.discovery, "discover", side_effect=self.discovery_result(None, [row])), \
             patch.object(candidate, "_relevant_inputs_match", return_value=True):
            result = candidate.resolve(base_pin=self.base, output_directory=self.output / "out",
                repository="owner/repo", branch="spike", current_run_id="999", selected_core=True)
        self.assertEqual(result["status"], "stale")
        self.assertIn("core-only", result["reason"])

    def test_accepts_checked_candidate_and_uses_run_attempt(self):
        with patch.object(candidate.discovery, "discover", side_effect=self.discovery_result(None, [self.row])), \
             patch.object(candidate, "_relevant_inputs_match", return_value=True):
            result = self.resolve()
        self.assertEqual(result["status"], "checked")
        target = json.loads(Path(result["target"]).read_text())
        self.assertEqual(target["build_id"], f"github-{self.run_id}-{self.attempt}")
        self.assertEqual(json.loads((self.output / "out/result.json").read_text())["status"], "checked")

    def test_rejects_wrong_head_and_changed_recipe(self):
        self.row["source"]["head_sha"] = "b" * 40
        with patch.object(candidate.discovery, "discover", side_effect=self.discovery_result(None, [self.row])), \
             patch.object(candidate, "_relevant_inputs_match", return_value=True):
            self.assertEqual(self.resolve()["status"], "stale")
        self.row["source"]["head_sha"] = self.revision
        with patch.object(candidate.discovery, "discover", side_effect=self.discovery_result(None, [self.row])), \
             patch.object(candidate, "_relevant_inputs_match", return_value=False):
            result = self.resolve()
        self.assertEqual(result["status"], "stale")
        self.assertIn("recipe", result["reason"])

    def test_reports_missing_candidate(self):
        with patch.object(candidate.discovery, "discover", side_effect=self.discovery_result(None, [])):
            self.assertEqual(self.resolve()["status"], "missing")


if __name__ == "__main__":
    unittest.main()
