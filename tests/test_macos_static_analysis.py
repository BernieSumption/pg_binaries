import importlib.util
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "scripts/macos/static_analysis.py"
SPEC = importlib.util.spec_from_file_location("macos_static_analysis", MODULE_PATH)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class Result:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class MacosStaticAnalysisTests(unittest.TestCase):
    def test_archive_evidence_binds_exact_bytes_and_rejects_duplicate_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "postgresql.tar.gz"
            archive.write_bytes(b"final archive")
            self.assertEqual(analysis.archive_evidence([archive]), [{
                "basename": archive.name,
                "sha256": hashlib.sha256(b"final archive").hexdigest(),
            }])
            with self.assertRaisesRegex(ValueError, "duplicate archive"):
                analysis.archive_evidence([archive, archive])

    def inspect_fixture(self, dependency="@loader_path/../lib/libpg.dylib", architecture="arm64", minos="11.0", rpath="@loader_path/../lib", dylib_id=None, link_target=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        binary = root / "bin/postgres"
        library = root / "lib/libpg.dylib"
        binary.parent.mkdir()
        library.parent.mkdir()
        binary.write_bytes(b"fake")
        library.write_bytes(b"fake")
        if link_target is not None:
            (root / "lib/alias.dylib").symlink_to(link_target)
        dependencies = {binary.resolve(): dependency, library.resolve(): "/usr/lib/libSystem.B.dylib"}

        def fake_run(*args):
            tool = args[0]
            if len(args) == 2 and args[1] in ("-v", "-version", "-V"):
                return Result(f"{tool} test version")
            path = Path(args[-1])
            if tool == "file":
                kind = "Mach-O 64-bit executable" if path == binary else "Mach-O 64-bit dynamically linked shared library"
                return Result(kind)
            if tool == "lipo":
                return Result(architecture)
            if tool == "otool" and args[1] == "-L":
                linked_path = dylib_id if path == library.resolve() and dylib_id else dependencies[path]
                return Result(f"{path}:\n\t{linked_path} (compatibility version 1.0.0, current version 1.0.0)\n")
            if tool == "otool" and args[1] == "-l":
                identifier = f"Load command 1\n          cmd LC_ID_DYLIB\n      cmdsize 48\n         name {dylib_id} (offset 24)\n" if path == library.resolve() and dylib_id else ""
                return Result(f"{identifier}Load command 2\n      cmd LC_RPATH\n  cmdsize 32\n     path {rpath} (offset 12)\nLoad command 3\n      cmd LC_BUILD_VERSION\n  cmdsize 32\n platform MACOS\n    minos {minos}\n      sdk 15.0\n    ntools 0\n")
            raise AssertionError(args)

        with patch.object(analysis, "run", side_effect=fake_run):
            return analysis.inspect(root, "arm64")

    def test_accepts_in_tree_loader_path_and_allowed_system_dependency(self):
        report = self.inspect_fixture()
        self.assertTrue(report["passed"], report["findings"])
        self.assertEqual(len(report["inspected_files"]), 2)

    def test_does_not_treat_dylib_install_id_as_import(self):
        report = self.inspect_fixture(dylib_id="@rpath/libpg.dylib")
        self.assertTrue(report["passed"], report["findings"])

    def test_rejects_wrong_architecture(self):
        report = self.inspect_fixture(architecture="x86_64")
        self.assertFalse(report["passed"])
        self.assertTrue(any(item["error"] == "required architecture missing" for item in report["findings"]))

    def test_rejects_absolute_external_dependency_and_too_new_target(self):
        report = self.inspect_fixture(dependency="/opt/homebrew/lib/libpg.dylib", minos="12.0")
        self.assertFalse(report["passed"])
        errors = {item["error"] for item in report["findings"]}
        self.assertIn("forbidden absolute dependency", errors)
        self.assertIn("minimum macOS target exceeds 11.0", errors)

    def test_rejects_unresolved_loader_path_and_external_rpath(self):
        report = self.inspect_fixture(dependency="@loader_path/missing.dylib", rpath="/opt/homebrew/lib")
        self.assertFalse(report["passed"])
        errors = {item["error"] for item in report["findings"]}
        self.assertIn("unresolved dependency", errors)
        self.assertIn("forbidden absolute LC_RPATH", errors)

    def test_checks_installation_links(self):
        report = self.inspect_fixture(link_target="libpg.dylib")
        self.assertTrue(report["passed"], report["findings"])
        self.assertEqual(len(report["installation_links"]), 1)

        report = self.inspect_fixture(link_target="/usr/lib/libSystem.B.dylib")
        self.assertFalse(report["passed"])
        self.assertTrue(any(item["error"] == "installation link leaves archive or is unresolved"
                            for item in report["findings"]))

        report = self.inspect_fixture(link_target="missing.dylib")
        self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()
