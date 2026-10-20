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
import windows_core_pin


class WindowsCoreCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / "out"
        self.version = "17.11"
        self.revision = "a" * 40
        self.run_id = 123456
        self.attempt = 2
        self.base = ROOT / f"support/windows-core-pins/{self.version}-x86_64.json"
        self.archive = Path(self.temp.name) / f"postgresql-{self.version}-windows-x86_64.tar.gz"
        src = source_archive.source_archive("postgresql", self.version, "tar.gz", ROOT)
        self.manifest = {
            "component": "postgresql", "version": self.version,
            "postgresql_version": self.version, "platform": "windows", "architecture": "x86_64",
            "build_id": f"github-{self.run_id}-{self.attempt}", "source_revision": self.revision,
            "source_archive": src, "source_sha256": src["sha256"],
            "build_configuration": (
                f"postgresql-{self.version};builder=windows-runner;meson=debugoptimized;"
                "postgresql=icu,lz4,zstd,zlib,openssl,libxml,libxslt,no-uuid,no-readline;"
                "compiler=MSVC;vcpkg=revision;runtime=vcpkg-and-msvc-dlls"),
        }
        self.write_archive()
        self.pin = {
            "schema_version": 1, "workflow": "postgresql-windows-selected-publication.yml",
            "run_id": self.run_id,
            "artifact_name": f"windows-core-selected-{self.version}-build-{self.run_id}",
            "archive_name": self.archive.name,
            "sha256": hashlib.sha256(self.archive.read_bytes()).hexdigest(),
        }
        self.run = {"head_sha": self.revision}

    def tearDown(self):
        self.temp.cleanup()

    def test_selected_publication_workflows_use_exact_optional_pins_without_push_triggers(self):
        for name in (
            "postgresql-windows-selected-publication.yml",
            "hypopg-windows-selected-publication.yml",
            "pg-jsonschema-windows-selected-publication.yml",
            "pgtap-windows-selected-publication.yml",
        ):
            with self.subTest(workflow=name):
                workflow = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
                self.assertIn("--artifact-pin \"support/windows-core-artifact-pins/$($env:PG_VERSION)-x86_64.json\"", workflow)
                self.assertNotIn("push:", workflow)

    def write_archive(self):
        body = json.dumps(self.manifest).encode()
        with tarfile.open(self.archive, "w:gz") as tar:
            info = tarfile.TarInfo("postgresql/manifest.json")
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        Path(str(self.archive) + ".sha256").write_text(f"{digest}  {self.archive.name}\n", encoding="ascii")

    def resolve(self, pin=None):
        with patch.object(candidate.core_pin, "load_artifact_pin", return_value=pin or self.pin), \
             patch.object(candidate, "_download_pin", return_value=(self.run, str(self.attempt), self.archive)), \
             patch.object(candidate, "_relevant_inputs_match", return_value=True):
            return candidate.resolve(base_pin=self.base, output_directory=self.output,
                repository="owner/repo", branch="spike", current_run_id="999", selected_core=True)

    def test_exact_pin_is_validated_and_provenance_is_recorded(self):
        result = self.resolve()
        self.assertEqual(result["status"], "checked")
        self.assertEqual(result["candidate_kind"], "selected")
        target = json.loads(Path(result["target"]).read_text())
        self.assertEqual(target["build_id"], f"github-{self.run_id}-{self.attempt}")
        self.assertEqual(target["source_revision"], self.revision)

    def test_missing_pin_does_not_download_and_reports_missing(self):
        with patch.object(candidate.core_pin, "load_artifact_pin",
                          side_effect=windows_core_pin.MissingArtifactPin("no exact pin")), \
             patch.object(candidate, "_download_pin") as download:
            result = candidate.resolve(base_pin=self.base, output_directory=self.output,
                repository="owner/repo", branch="spike", current_run_id="999", selected_core=True)
        self.assertEqual(result["status"], "missing")
        download.assert_not_called()

    def test_expired_or_unavailable_pin_falls_back_to_rebuild(self):
        with patch.object(candidate.core_pin, "load_artifact_pin", return_value=self.pin), \
             patch.object(candidate, "_download_pin", side_effect=FileNotFoundError("artifact expired")):
            result = candidate.resolve(base_pin=self.base, output_directory=self.output,
                repository="owner/repo", branch="spike", current_run_id="999", selected_core=True)
        self.assertEqual(result["status"], "missing")
        self.assertIn("expired", result["reason"])

    def test_exact_run_is_checked_before_archive_download(self):
        run = {
            "id": self.run_id, "run_attempt": self.attempt,
            "repository": {"full_name": "owner/repo"},
            "head_repository": {"full_name": "owner/repo"},
            "head_branch": "spike", "event": "workflow_dispatch",
            "status": "completed", "conclusion": "success",
            "path": ".github/workflows/selected-extension-publication.yml",
            "head_sha": self.revision,
        }
        from types import SimpleNamespace

        def fake_run(args, **kwargs):
            if args[1] == "api":
                return SimpleNamespace(returncode=0, stdout=json.dumps(run), stderr="")
            download_dir = Path(args[-1])
            (download_dir / self.archive.name).write_bytes(self.archive.read_bytes())
            Path(str(download_dir / self.archive.name) + ".sha256").write_bytes(
                Path(str(self.archive) + ".sha256").read_bytes())
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(candidate.subprocess, "run", side_effect=fake_run):
            checked_run, attempt, archive = candidate._download_pin(
                self.pin, self.output, "owner/repo", "spike", "999")
        self.assertEqual(checked_run["head_sha"], self.revision)
        self.assertEqual(attempt, str(self.attempt))
        self.assertEqual(Path(archive).read_bytes(), self.archive.read_bytes())

    def test_dispatcher_path_is_not_accepted_for_nonselected_pin(self):
        run = {
            "id": self.run_id, "run_attempt": self.attempt,
            "repository": {"full_name": "owner/repo"},
            "head_repository": {"full_name": "owner/repo"},
            "head_branch": "spike", "event": "workflow_dispatch",
            "status": "completed", "conclusion": "success",
            "path": ".github/workflows/selected-extension-publication.yml",
            "head_sha": self.revision,
        }
        pilot = dict(self.pin, workflow="windows-pilot.yml")
        with patch.object(candidate, "_run_json", return_value=run), \
             patch.object(candidate.subprocess, "run") as download:
            with self.assertRaisesRegex(ValueError, "builder run"):
                candidate._download_pin(pilot, self.output, "owner/repo", "spike", "999")
        download.assert_not_called()

    def test_pinned_run_identity_mismatch_is_rejected(self):
        from types import SimpleNamespace

        with patch.object(candidate, "_run_json", return_value={"id": self.run_id,
                "repository": {"full_name": "other/repo"}}), \
             patch.object(candidate.subprocess, "run") as download:
            with self.assertRaisesRegex(ValueError, "builder run"):
                candidate._download_pin(self.pin, self.output, "owner/repo", "spike", "999")
        download.assert_not_called()

    def test_archive_provenance_mismatch_is_stale(self):
        self.run = {"head_sha": "b" * 40}
        result = self.resolve()
        self.assertEqual(result["status"], "stale")
        self.assertIn("head SHA", result["reason"])

    def test_selected_publication_rejects_pilot_pin(self):
        pilot = dict(self.pin, workflow="windows-pilot.yml",
                     artifact_name=f"windows-postgresql-{self.version}-pilot")
        result = self.resolve(pin=pilot)
        self.assertEqual(result["status"], "stale")
        self.assertIn("selected publication requires", result["reason"])


if __name__ == "__main__":
    unittest.main()
