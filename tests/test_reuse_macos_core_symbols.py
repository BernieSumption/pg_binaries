import io
import json
import tempfile
import tarfile
import unittest
from pathlib import Path
import sys
import subprocess
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import reuse_macos_core_symbols as reuse


class ReuseMacOSCoreSymbolsTests(unittest.TestCase):
    def _init_git(self, root, files):
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-qm", "base"], cwd=root, check=True)
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                              capture_output=True, text=True).stdout.strip()

    def test_unrelated_release_snapshot_change_preserves_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "support").mkdir()
            snapshot = root / "support/postgresql-releases.json"
            snapshot.write_text('{"18.6": "old"}\n')
            workflow = root / reuse.CORE_WORKFLOW
            workflow.parent.mkdir(parents=True)
            workflow.write_text("jobs:\n  build:\n    steps: [build]\n  verify:\n    steps: [verify v1]\n")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                            "commit", "-qm", "base"], cwd=root, check=True)
            revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                                      capture_output=True, text=True).stdout.strip()
            snapshot.write_text('{"18.6": "new"}\n')
            self.assertTrue(reuse.relevant_inputs_match(revision, root))

    def test_core_recipe_change_rejects_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recipe = root / "tools/create_macos_symbols.py"
            recipe.parent.mkdir()
            recipe.write_text("recipe v1\n")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "tools/create_macos_symbols.py"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                            "commit", "-qm", "base"], cwd=root, check=True)
            revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                                      capture_output=True, text=True).stdout.strip()
            recipe.write_text("recipe v2\n")
            self.assertFalse(reuse.relevant_inputs_match(revision, root))

    def test_verifier_workflow_changes_preserve_reuse_but_build_changes_reject_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workflow = "jobs:\n  build:\n    steps: [build v1]\n  verify:\n    steps: [verify v1]\n"
            revision = self._init_git(root, {reuse.CORE_WORKFLOW: workflow})
            path = root / reuse.CORE_WORKFLOW
            path.write_text(workflow.replace("verify v1", "verify v2"))
            self.assertTrue(reuse.relevant_inputs_match(revision, root))
            path.write_text(workflow.replace("build v1", "build v2").replace("verify v1", "verify v2"))
            self.assertFalse(reuse.relevant_inputs_match(revision, root))

    def test_historical_passed_profile_record_can_be_reused(self):
        revision = "a" * 40
        archive_sha256 = "b" * 64
        record = {
            "schema_version": 2, "scope": "publication", "component": "postgresql",
            "outcome": "passed", "profile_id": "postgresql-publication-macos-arm64-18.6",
            "profile_revision": "c" * 64, "test_cases": ["old-archive-suite", "old-symbols"],
            "case_results": {"old-archive-suite": "passed", "old-symbols": "passed"},
            "postgresql_version": "18.6", "platform": "macos-arm64",
            "sha256": archive_sha256, "test_revision": revision,
            "ci": {"source_revision": revision, "build_revision": revision,
                   "test_revision": revision, "run_id": "123"},
            "environment": {"os": "macos", "architecture": "arm64", "endpoint": "current",
                            "clean_system": True, "dependency_checks_passed": True},
        }
        cases = reuse.validate_passing_record(
            record, profile_id=record["profile_id"], version="18.6", architecture="arm64",
            run_id="123", revision=revision, archive_sha256=archive_sha256)
        self.assertEqual(cases, ("old-archive-suite", "old-symbols"))

    def test_failed_or_wrong_identity_record_is_rejected(self):
        revision = "a" * 40
        record = {
            "schema_version": 2, "scope": "publication", "component": "postgresql",
            "outcome": "passed", "profile_id": "profile", "profile_revision": "c" * 64,
            "test_cases": ["archive-suite"], "case_results": {"archive-suite": "passed"},
            "postgresql_version": "18.6", "platform": "macos-arm64", "sha256": "b" * 64,
            "test_revision": revision,
            "ci": {"source_revision": revision, "build_revision": revision,
                   "test_revision": revision, "run_id": "123"},
            "environment": {"os": "macos", "architecture": "arm64", "endpoint": "current",
                            "clean_system": True, "dependency_checks_passed": True},
        }
        args = dict(profile_id="profile", version="18.6", architecture="arm64", run_id="123",
                    revision=revision, archive_sha256="b" * 64)
        record["outcome"] = "failed"
        record["case_results"]["archive-suite"] = "failed"
        with self.assertRaisesRegex(RuntimeError, "passed record"):
            reuse.validate_passing_record(record, **args)
        record["outcome"] = "passed"
        record["case_results"]["archive-suite"] = "passed"
        record["sha256"] = "d" * 64
        with self.assertRaisesRegex(RuntimeError, "passed record"):
            reuse.validate_passing_record(record, **args)
        record["sha256"] = "b" * 64
        record["ci"]["run_id"] = "456"
        with self.assertRaisesRegex(RuntimeError, "provenance"):
            reuse.validate_passing_record(record, **args)

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
                manifest["source_archive"] = dict(source, sha256="c" * 64)
                encoded = json.dumps(manifest).encode()
                with tarfile.open(archive, "w:gz") as bundle:
                    info = tarfile.TarInfo("postgresql/manifest.json")
                    info.size = len(encoded)
                    bundle.addfile(info, io.BytesIO(encoded))
                with self.assertRaisesRegex(RuntimeError, "manifest"):
                    reuse.validate_core_manifest(archive, version, architecture, run_id, attempt,
                                                 revision, Path(temporary))
                manifest["source_archive"] = source
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
                archive.writestr(f"pg_binaries/pg_binaries/support/verification/{filename}", body)
            reuse.extract_zip(data.getvalue(), root)
            self.assertEqual(reuse._artifact_file(root, filename), body)
            (root / "pg_binaries/pg_binaries/support/verification" / filename).write_bytes(b'{"outcome":"failed"}')
            with self.assertRaisesRegex(RuntimeError, "copies disagree"):
                reuse._artifact_file(root, filename)

    def test_finds_attempt_in_real_temp_layout_and_checks_retained_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            name = "publication-attempt.json"
            body = b'{"run_id":"123"}'
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as archive:
                archive.writestr(f"_temp/verification/{name}", body)
                archive.writestr(
                    f"pg_binaries/pg_binaries/support/evidence/macos-core-publication-123/"
                    f"postgresql-18.6/arm64/{name}", body)
            reuse.extract_zip(data.getvalue(), root)
            self.assertEqual(reuse._artifact_file(root, name), body)
            retained = root / "pg_binaries/pg_binaries/support/evidence/macos-core-publication-123/postgresql-18.6/arm64" / name
            retained.write_bytes(b'{"run_id":"456"}')
            with self.assertRaisesRegex(RuntimeError, "copies disagree"):
                reuse._artifact_file(root, name)


if __name__ == "__main__":
    unittest.main()
