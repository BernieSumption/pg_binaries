import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import check_elf_dependencies as checker


class ElfInspectionTests(unittest.TestCase):
    def inspect(self, machine, program, dynamic):
        outputs = {"-hW": f"  Machine:                           {machine}\n",
                   "-lW": program, "-dW": dynamic}

        def run(command, **kwargs):
            option = next(arg for arg in command if arg in outputs)
            return subprocess.CompletedProcess(command, 0, outputs[option], "")

        with patch.object(checker.subprocess, "run", side_effect=run):
            return checker.inspect_elf(Path("fixture"))

    def test_reads_architecture_interpreter_and_both_search_path_tags(self):
        result = self.inspect(
            "AArch64",
            "[Requesting program interpreter: /lib/ld-linux-aarch64.so.1]\n",
            " 0x000000000000000f (RPATH)              Library rpath: [$ORIGIN/../lib]\n"
            " 0x000000000000001d (RUNPATH)            Library runpath: [$ORIGIN/plugins:/opt/host]\n",
        )
        self.assertEqual(result, ("arm64", "/lib/ld-linux-aarch64.so.1",
                                  ["$ORIGIN/../lib", "$ORIGIN/plugins", "/opt/host"]))

    def test_rejects_unknown_machine(self):
        with self.assertRaisesRegex(ValueError, "unsupported or unrecognized"):
            self.inspect("RISC-V", "", "")

    def test_accepts_origin_path_resolving_inside_installation(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp).resolve()
            binary = prefix / "bin/tool"
            binary.parent.mkdir()
            checker.validate_paths(binary, prefix, "x86_64", None, ["$ORIGIN/../lib"])

    def test_rejects_absolute_and_escaping_search_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp).resolve()
            binary = prefix / "bin/tool"
            binary.parent.mkdir()
            for search_path in ("/opt/host/lib", "$ORIGIN/../../../outside", "$ORIGINsuffix"):
                with self.subTest(search_path=search_path), self.assertRaises(ValueError):
                    checker.validate_paths(binary, prefix, "x86_64", None, [search_path])


VERSION_NEEDS = """Version needs section '.gnu.version_r' contains 1 entry:
 Addr: 0x0000000000000800  Offset: 0x000800  Link: 7 (.dynstr)
  0x000000: Version: 1  File: libc.so.6  Cnt: 2
  0x0010:   Name: GLIBC_2.34  Flags: none  Version: 3
  0x0020:   Name: GLIBC_2.2.5  Flags: WEAK  Version: 2
"""


class SymbolVersionTests(unittest.TestCase):
    def inspect(self, output, stderr=""):
        result = subprocess.CompletedProcess([], 0, output, stderr)
        with patch.object(checker.subprocess, "run", return_value=result) as run:
            parsed = checker.symbol_version_requirements(Path("fixture"))
        self.assertEqual(run.call_args.args[0], ["readelf", "-VW", "fixture"])
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")
        return parsed

    def test_records_library_versions_and_weak_flags(self):
        self.assertEqual(self.inspect(VERSION_NEEDS), [{"library": "libc.so.6", "versions": [
            {"name": "GLIBC_2.34", "flags": "none", "index": 3},
            {"name": "GLIBC_2.2.5", "flags": "WEAK", "index": 2},
        ]}])

    def test_accepts_explicit_absence_of_versions(self):
        self.assertEqual(self.inspect("No version information found in this file.\n"), [])

    def test_rejects_malformed_and_incomplete_output(self):
        for output in ("", "unrecognized", VERSION_NEEDS.replace("Cnt: 2", "Cnt: 3"),
                       VERSION_NEEDS.replace("contains 1 entry", "contains 2 entries"),
                       VERSION_NEEDS.replace("Name: GLIBC_2.34", "Broken: GLIBC_2.34")):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.inspect(output)
        with self.assertRaisesRegex(ValueError, "diagnostics"):
            self.inspect(VERSION_NEEDS, "readelf: corrupt version table")

    def test_unavailable_version_inspection_fails(self):
        with patch.object(checker.subprocess, "run", side_effect=FileNotFoundError("readelf")):
            with self.assertRaises(FileNotFoundError):
                checker.symbol_version_requirements(Path("fixture"))


class DependencyClosureTests(unittest.TestCase):
    def check_fixture(self, bundled_loader, external_library, search_paths=None):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp).resolve()
            binary = prefix / "tool"
            binary.write_bytes(b"\x7fELFfixture")
            if bundled_loader:
                loader = prefix / "lib/glibc/ld-linux-x86-64.so.2"
                loader.parent.mkdir(parents=True)
                loader.write_bytes(b"\x7fELFfixture")
            external = prefix.parent / (prefix.name + "-external.so")
            external.write_bytes(b"fixture")
            try:
                dependency_output = (f"{external_library}\n" if external_library.endswith("=> not found")
                                     else f"{external_library} => {external} (0x456)\n")
                output = f"libdirect.so => {prefix}/libdirect.so (0x123)\n{dependency_output}"
                (prefix / "libdirect.so").write_bytes(b"fixture")
                report = {"inspected_files": [], "files": []}
                with patch.object(checker, "inspect_elf", return_value=("x86_64", None, search_paths or [])), \
                        patch.object(checker, "symbol_version_requirements", return_value=[{"library": "libc.so.6", "versions": []}]), \
                        patch.object(checker, "static_executable", return_value=False), \
                        patch.object(checker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
                    checker.check(prefix, "x86_64", report)
                return report
            finally:
                external.unlink()

    def test_rejects_transitive_unbundled_dependency(self):
        with self.assertRaisesRegex(ValueError, "unbundled dependency: libtransitive.so"):
            self.check_fixture(True, "libtransitive.so")

    def test_bundled_loader_rejects_external_libc(self):
        with self.assertRaisesRegex(ValueError, "unbundled dependency: libc.so.6"):
            self.check_fixture(True, "libc.so.6")

    def test_rejects_dependency_missing_from_bundled_runtime(self):
        with self.assertRaisesRegex(ValueError, "libtransitive.so => not found"):
            self.check_fixture(True, "libtransitive.so => not found")

    def test_rejects_nonrelocatable_search_path_during_archive_check(self):
        with self.assertRaisesRegex(ValueError, "non-relocatable ELF runtime search path"):
            self.check_fixture(False, "libc.so.6", ["/opt/build/lib"])

    def test_system_libc_boundary_without_bundled_loader(self):
        report = self.check_fixture(False, "libc.so.6")
        self.assertEqual(report["files"][0]["symbol_version_requirements"],
                         [{"library": "libc.so.6", "versions": []}])


class ArchiveReportTests(unittest.TestCase):
    def test_archive_evidence_binds_basename_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "final.tar.gz"
            archive.write_bytes(b"final archive bytes")
            self.assertEqual(checker.archive_evidence([archive]), [{
                "basename": "final.tar.gz",
                "sha256": hashlib.sha256(b"final archive bytes").hexdigest(),
            }])

    def test_archive_evidence_rejects_duplicate_basenames(self):
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first" / "same.tar.gz"
            second = Path(temp) / "second" / "same.tar.gz"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            with self.assertRaisesRegex(ValueError, "duplicate archive basename"):
                checker.archive_evidence([first, second])

    def test_archive_evidence_rejects_missing_or_non_file_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with self.assertRaisesRegex(ValueError, "missing or not a regular file"):
                checker.archive_evidence([directory / "missing.tar.gz"])
            with self.assertRaisesRegex(ValueError, "missing or not a regular file"):
                checker.archive_evidence([directory])

    def test_report_cli_accepts_repeated_archives(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = root / "a.tar.gz", root / "b.tar.gz"
            first.write_bytes(b"archive a")
            second.write_bytes(b"archive b")
            report_path = root / "report.json"
            argv = ["checker", str(root), "--report", str(report_path),
                    "--archive", str(first), "--archive", str(second)]
            readelf_version = subprocess.CompletedProcess([], 0, "GNU readelf 2.40\n", "")
            with patch.object(sys, "argv", argv), \
                    patch.object(checker.subprocess, "run", return_value=readelf_version), \
                    patch.object(checker, "check", return_value=3):
                self.assertEqual(checker.main(), 0)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["archives"], [
                {"basename": "a.tar.gz", "sha256": hashlib.sha256(b"archive a").hexdigest()},
                {"basename": "b.tar.gz", "sha256": hashlib.sha256(b"archive b").hexdigest()},
            ])

    def test_rejects_wrong_or_missing_bundled_interpreter(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp).resolve()
            (prefix / "lib/glibc").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "forbidden ELF interpreter"):
                checker.validate_paths(Path(temp) / "bin/tool", prefix, "x86_64",
                                       "/lib/ld-linux-aarch64.so.1", [])
            with self.assertRaisesRegex(ValueError, "no bundled loader"):
                checker.validate_paths(Path(temp) / "bin/tool", prefix, "x86_64",
                                       "/lib64/ld-linux-x86-64.so.2", [])


if __name__ == "__main__":
    unittest.main()
