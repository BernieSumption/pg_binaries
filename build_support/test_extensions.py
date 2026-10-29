from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from build_support.extensions import build_extension, prepare_workspace
from build_support.sources import sha256


class ExtensionWorkspaceTests(unittest.TestCase):
    def test_default_workspace_is_not_uploaded_with_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            development = Path(temporary) / "development.tar.gz"
            development.write_bytes(b"development archive")
            runtime = {"filename": "postgresql-18.6-linux-arm64.tar.gz", "sha256": "a" * 64}

            def prepare(workspace, *args):
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
