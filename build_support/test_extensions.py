from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

from build_support.extensions import build_extension, prepare_workspace
from build_support.sources import sha256
from build_support.iteration import WorkspaceLock, development_identity, iteration_keys


class ExtensionWorkspaceTests(unittest.TestCase):
    def test_fresh_workspace_prepares_sources_postgresql_and_empty_stages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            development = root / "development"
            development.mkdir()
            workspace = root / "workspace"
            metadata = {"sources": {"source": {"sha256": "a" * 64}}}

            def prepare_sources(sources, destination, _cache):
                (destination / "source").mkdir(parents=True)

            def prepare_development(_source, destination):
                destination.mkdir()

            with patch("build_support.extensions.prepare_sources", side_effect=prepare_sources), \
                    patch("build_support.postgresql.prepare_development", side_effect=prepare_development):
                prepared = prepare_workspace(workspace, development, metadata, root / "cache")

            self.assertEqual(prepared, workspace.resolve())
            self.assertTrue((workspace / "sources/source").is_dir())
            self.assertTrue((workspace / "postgresql").is_dir())
            self.assertEqual(list((workspace / "build").iterdir()), [])
            self.assertEqual(list((workspace / "payload").iterdir()), [])

    def test_reuse_requires_explicit_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "requires --workspace"):
                build_extension("pgvector", "linux-arm64", Path(temporary), Path(temporary), reuse_workspace=True)
            with self.assertRaisesRegex(ValueError, "absolute --workspace"):
                build_extension("pgvector", "linux-arm64", Path(temporary), Path(temporary),
                                Path("relative-workspace"), reuse_workspace=True)

    def test_whitespace_workspace_is_rejected_before_source_preparation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("build_support.extensions.prepare_sources") as prepare:
                with self.assertRaisesRegex(ValueError, "without whitespace"):
                    prepare_workspace(root / "build with spaces", root / "development", {}, root / "cache")
                prepare.assert_not_called()

    def test_default_workspace_is_not_uploaded_with_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            development = Path(temporary) / "development.tar.gz"
            development.write_bytes(b"development archive")
            runtime = {"filename": "postgresql-18.6-linux-arm64.tar.gz", "sha256": "a" * 64}

            def prepare(workspace, *args):
                self.addCleanup(shutil.rmtree, workspace)
                share = workspace / "postgresql/share"
                share.mkdir(parents=True)
                (share / "pg_build_paths.json").write_text(json.dumps({"runtime_archive": runtime}))
                return workspace

            def finish(workspace, target, destination, package, version):
                self.assertNotIn(output, workspace.parents)
                archive = destination / "pgvector-postgresql-18.6-linux-arm64.tar.gz"
                archive.write_bytes(b"archive")
                return archive

            with patch("build_support.extensions.prepare_workspace", side_effect=prepare), \
                    patch("build_support.extensions.subprocess.run"), \
                    patch("build_support.extensions.subprocess.check_output", return_value="PostgreSQL 18.6\n"), \
                    patch("build_support.bundling.finish_extension", side_effect=finish):
                build_extension("pgvector", "linux-arm64", development, output)
            self.assertEqual({path.name for path in output.iterdir()}, {
                "pgvector-postgresql-18.6-linux-arm64.tar.gz", "extension-build.json"})
            manifest = json.loads((output / "extension-build.json").read_text())
            self.assertEqual(manifest["postgresql_archive"], runtime)
            self.assertEqual(manifest["postgresql_development_archive"]["sha256"], sha256(development))

    def test_workspace_cannot_be_inside_development_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            with self.assertRaisesRegex(ValueError, "development input must be outside"):
                prepare_workspace(source / "nested", source, {}, source.parent / "cache")

    def test_reuse_keeps_dependency_prefix_and_clears_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            keys = {"source_key": "source", "context_key": "context", "dependency_key": "deps", "main_key": "main"}
            from build_support.iteration import prepare_reused_workspace, record_dependency_success
            prepare_reused_workspace(workspace, "demo", "linux-arm64", keys)
            (workspace / "build/dependencies").mkdir()
            (workspace / "build/dependencies/ready").write_text("ok")
            (workspace / "build/target").mkdir()
            (workspace / "build/target/objects").write_text("cached")
            (workspace / "payload/stale").write_text("stale")
            record_dependency_success(workspace, "deps")
            prepare_reused_workspace(workspace, "demo", "linux-arm64", keys)
            self.assertTrue((workspace / "build/dependencies/ready").is_file())
            self.assertTrue((workspace / "build/target/objects").is_file())
            self.assertEqual(list((workspace / "payload").iterdir()), [])

    def test_main_recipe_change_keeps_successful_dependencies_and_rust_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            from build_support.iteration import prepare_reused_workspace, record_dependency_success
            prepare_reused_workspace(workspace, "demo", "linux-arm64",
                                     {"source_key": "s", "context_key": "c", "dependency_key": "d", "main_key": "m1"})
            for relative in ("dependencies/ready", "target/object", "pgrx/state", "stage/stale"):
                path = workspace / "build" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("cached")
            record_dependency_success(workspace, "d")
            prepare_reused_workspace(workspace, "demo", "linux-arm64",
                                     {"source_key": "s", "context_key": "c", "dependency_key": "d", "main_key": "m2"})
            self.assertTrue((workspace / "build/dependencies/ready").is_file())
            self.assertTrue((workspace / "build/target/object").is_file())
            self.assertTrue((workspace / "build/pgrx/state").is_file())
            self.assertFalse((workspace / "build/stage").exists())

    def test_dependency_change_discards_old_dependency_and_main_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            from build_support.iteration import prepare_reused_workspace, record_dependency_success
            prepare_reused_workspace(workspace, "demo", "linux-arm64",
                                     {"source_key": "s", "context_key": "c", "dependency_key": "d1", "main_key": "m"})
            (workspace / "build/dependencies/ready").parent.mkdir(parents=True)
            (workspace / "build/dependencies/ready").write_text("old")
            record_dependency_success(workspace, "d1")
            prepare_reused_workspace(workspace, "demo", "linux-arm64",
                                     {"source_key": "s", "context_key": "c", "dependency_key": "d2", "main_key": "m"})
            self.assertFalse((workspace / "build/dependencies/ready").exists())

    def test_dependency_key_tracks_dependency_recipe_postgresql_and_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            package.mkdir()
            (package / "build.sh").write_text("main one")
            (package / "build-dependencies.sh").write_text("dependencies one")
            development = root / "development"
            development.mkdir()
            (development / "version").write_text("1")
            metadata = {"sources": {"src": {"sha256": "a" * 64}}}
            environment = {"CC": "cc", "CFLAGS": "-O2"}
            with patch("build_support.iteration._compiler_identity", return_value={"CC": "test"}):
                base = iteration_keys("demo", "linux-arm64", metadata, development_identity(development),
                                      package, environment)
                (package / "build.sh").write_text("main two")
                main_changed = iteration_keys("demo", "linux-arm64", metadata, development_identity(development),
                                              package, environment)
                self.assertEqual(base["dependency_key"], main_changed["dependency_key"])
                self.assertNotEqual(base["main_key"], main_changed["main_key"])
                (package / "build-dependencies.sh").write_text("dependencies two")
                recipe_changed = iteration_keys("demo", "linux-arm64", metadata, development_identity(development),
                                                package, environment)
                self.assertNotEqual(base["dependency_key"], recipe_changed["dependency_key"])
                (package / "build-dependencies.sh").write_text("dependencies one")
                (development / "version").write_text("2")
                pg_changed = iteration_keys("demo", "linux-arm64", metadata, development_identity(development),
                                            package, environment)
                self.assertNotEqual(base["context_key"], pg_changed["context_key"])
                settings_changed = iteration_keys("demo", "linux-arm64", metadata, development_identity(development),
                                                  package, {"CC": "cc", "CFLAGS": "-O0"})
                self.assertNotEqual(base["context_key"], settings_changed["context_key"])

    def test_wrong_workspace_and_concurrent_reuse_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            from build_support.iteration import prepare_reused_workspace
            prepare_reused_workspace(workspace, "demo", "linux-arm64",
                                     {"source_key": "s", "context_key": "c", "dependency_key": None, "main_key": "m"})
            with self.assertRaisesRegex(ValueError, "belongs to"):
                prepare_reused_workspace(workspace, "other", "linux-arm64",
                                         {"source_key": "s", "context_key": "c", "dependency_key": None, "main_key": "m"})
            with WorkspaceLock(workspace):
                with self.assertRaisesRegex(ValueError, "workspace is locked"):
                    with WorkspaceLock(workspace):
                        pass

    def test_dependency_phase_failure_is_not_cached(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "packages/demo"
            package_dir.mkdir(parents=True)
            (package_dir / "build.sh").write_text("main")
            (package_dir / "build-dependencies.sh").write_text("deps")
            development = root / "development"
            development.mkdir()
            workspace = root / "workspace"
            calls = []

            def run(command, **kwargs):
                calls.append(command[1])
                if command[1].endswith("build-dependencies.sh"):
                    raise __import__("subprocess").CalledProcessError(1, command)

            with patch("build_support.extensions.ROOT", root), \
                    patch("build_support.extensions.load_package", return_value={"sources": {"source": {"sha256": "a" * 64}}}), \
                    patch("build_support.extensions.prepare_sources", side_effect=lambda sources, dest, cache: (dest / "source").mkdir(parents=True)), \
                    patch("build_support.extensions._prepare_postgresql"), \
                    patch("build_support.iteration._compiler_identity", return_value={}), \
                    patch("build_support.extensions.subprocess.run", side_effect=run):
                with self.assertRaises(__import__("subprocess").CalledProcessError):
                    build_extension("demo", "linux-arm64", development, root / "output", workspace,
                                    root / "cache", True)
            marker = json.loads((workspace / ".pg-binaries-extension-workspace.json").read_text())
            self.assertNotIn("dependency_success_key", marker)
            self.assertEqual(len(calls), 1)

    def test_successful_dependency_phase_is_skipped_on_repeated_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "packages/demo"
            package_dir.mkdir(parents=True)
            (package_dir / "build.sh").write_text("main")
            (package_dir / "build-dependencies.sh").write_text("deps")
            development = root / "development"
            development.mkdir()
            workspace, output = root / "workspace", root / "output"
            calls = []

            def prepare_postgresql(_development, destination):
                shutil.rmtree(destination / "postgresql", ignore_errors=True)
                share = destination / "postgresql/share"
                share.mkdir(parents=True)
                (share / "pg_build_paths.json").write_text(json.dumps({"runtime_archive": {"filename": "pg.tar.gz"}}))

            def run(command, **kwargs):
                calls.append(Path(command[1]).name)

            def finish(_workspace, _target, destination, _package, _version):
                destination.mkdir(parents=True, exist_ok=True)
                archive = destination / "demo.tar.gz"
                archive.write_bytes(b"archive")
                return archive

            with patch("build_support.extensions.ROOT", root), \
                    patch("build_support.extensions.load_package", return_value={"sources": {"source": {"sha256": "a" * 64}}}), \
                    patch("build_support.extensions.prepare_sources", side_effect=lambda sources, dest, cache: (dest / "source").mkdir(parents=True)), \
                    patch("build_support.extensions._prepare_postgresql", side_effect=prepare_postgresql), \
                    patch("build_support.iteration._compiler_identity", return_value={}), \
                    patch("build_support.extensions.subprocess.run", side_effect=run), \
                    patch("build_support.extensions.subprocess.check_output", return_value="PostgreSQL 18.6\n"), \
                    patch("build_support.bundling.finish_extension", side_effect=finish):
                for _ in range(2):
                    build_extension("demo", "linux-arm64", development, output, workspace,
                                    root / "cache", True)
            self.assertEqual(calls.count("build-dependencies.sh"), 1)
            self.assertEqual(calls.count("build.sh"), 2)
