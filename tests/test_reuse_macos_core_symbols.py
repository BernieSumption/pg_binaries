import io
import json
import tempfile
import tarfile
import unittest
from pathlib import Path
import sys
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import reuse_macos_core_symbols as reuse


class ReuseMacOSCoreSymbolsTests(unittest.TestCase):
    def test_candidate_requires_successful_other_run_on_same_branch_and_workflow(self):
        run = {"id": 12, "status": "completed", "conclusion": "success",
               "head_branch": "spike",
               "repository": {"full_name": "owner/repo"},
               "head_repository": {"full_name": "owner/repo"}, "event": "push",
               "head_sha": "a" * 40,
               "path": ".github/workflows/postgresql-macos-selected-publication.yml"}
        self.assertTrue(reuse._matches(run, "owner/repo", "spike", "13", run["path"]))
        self.assertFalse(reuse._matches(run, "owner/repo", "other", "13", run["path"]))
        self.assertFalse(reuse._matches(run, "owner/repo", "spike", "12", run["path"]))
        self.assertFalse(reuse._matches(dict(run, conclusion="failure"), "owner/repo", "spike", "13", run["path"]))

    def test_embedded_manifest_binds_run_recipe_and_source(self):
        version, architecture, run_id, attempt, revision = "18.6", "arm64", "123", 2, "a" * 40
        configuration = (
            "postgresql-18.6;mode=core-only;builder=native-macos;deployment-target=11.0;"
            "configure=icu,openssl,lz4,zstd,libxml,libxslt,zlib,uuid-e2fs-interface-apple-system,no-readline;"
            "dependencies=pinned-upstream-source;cflags=-O2,-g;runtime=bundled-dylibs"
        )
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "core.tar.gz"
            source = {"url": "https://example.invalid/postgresql.tar.bz2", "sha256": "b" * 64}
            manifest = {"component": "postgresql", "version": version,
                        "postgresql_version": version, "platform": "macos",
                        "architecture": architecture, "build_id": f"github-{run_id}-{attempt}",
                        "source_revision": revision, "build_configuration": configuration,
                        "source_archive": source}
            encoded = json.dumps(manifest).encode()
            with tarfile.open(archive, "w:gz") as bundle:
                info = tarfile.TarInfo("postgresql/manifest.json")
                info.size = len(encoded)
                bundle.addfile(info, io.BytesIO(encoded))
            with patch.object(reuse.source_archive, "source_archive", return_value=source):
                reuse.validate_core_manifest(archive, version, architecture, run_id, attempt,
                                             revision, Path(temporary))
                manifest["build_id"] = "github-999-1"
                encoded = json.dumps(manifest).encode()
                with tarfile.open(archive, "w:gz") as bundle:
                    info = tarfile.TarInfo("postgresql/manifest.json")
                    info.size = len(encoded)
                    bundle.addfile(info, io.BytesIO(encoded))
                with self.assertRaisesRegex(RuntimeError, "manifest"):
                    reuse.validate_core_manifest(archive, version, architecture, run_id, attempt,
                                                 revision, Path(temporary))

    def test_failed_dsym_staging_does_not_create_build_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "core.tar.gz"
            sidecar = root / "core.tar.gz.sha256"
            archive.write_bytes(b"archive")
            sidecar.write_text("sidecar")
            destination = root / "archives"
            with patch.object(reuse.stage_symbols, "stage", side_effect=RuntimeError("bad dSYM")):
                with self.assertRaisesRegex(RuntimeError, "bad dSYM"):
                    reuse.stage_and_promote(root, archive, sidecar, archive.name, destination)
            self.assertFalse(destination.exists())

    def test_extracts_safe_artifact_members(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("debug-symbols/index.json", "{}")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "artifact"
            reuse.extract_zip(data.getvalue(), destination)
            self.assertEqual((destination / "debug-symbols/index.json").read_text(), "{}")

    def test_rejects_traversal_and_syntactic_alias_zip_paths(self):
        for name in ("../escape", "a//b", "a/./b"):
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as archive:
                archive.writestr(name, "x")
            with tempfile.TemporaryDirectory() as temporary:
                with self.assertRaises(RuntimeError):
                    reuse.extract_zip(data.getvalue(), Path(temporary) / "artifact")

    def test_finds_record_in_real_temp_layout_and_checks_retained_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            filename = "postgresql-18.6-macos-arm64-current-123.json"
            body = b'{"outcome":"passed"}'
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as archive:
                archive.writestr(f"_temp/verification/{filename}", body)
                archive.writestr(f"support/verification/{filename}", body)
            reuse.extract_zip(data.getvalue(), root)
            self.assertEqual(reuse._artifact_file(root, filename), body)
            (root / "support/verification" / filename).write_bytes(b'{"outcome":"failed"}')
            with self.assertRaisesRegex(RuntimeError, "copies disagree"):
                reuse._artifact_file(root, filename)


if __name__ == "__main__":
    unittest.main()
