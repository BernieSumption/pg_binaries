import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import check_pe_dependencies as checker


class DumpbinParserTests(unittest.TestCase):
    def test_parses_amd64_pe32_plus_and_windows_10_headers(self):
        output = """
            8664 machine (x64)
             20B magic # (PE32+)
            10.00 operating system version
            6.00 subsystem version
        """
        self.assertEqual(checker.parse_headers(output), {
            "machine": "AMD64", "optional_header": "PE32+",
            "os_version": "10.00", "subsystem_version": "6.00"})

    def test_rejects_wrong_architecture_and_higher_target(self):
        with self.assertRaisesRegex(ValueError, "machine/magic"):
            checker.parse_headers("14C machine (x86)\n 10B magic # (PE32)\n")
        too_new = "8664 machine (x64)\n20B magic # (PE32+)\n10.01 operating system version\n6.00 subsystem version\n"
        with self.assertRaisesRegex(ValueError, "exceeds Windows 10 floor"):
            checker.parse_headers(too_new)

    def test_parses_normal_and_delay_import_names(self):
        output = """
          Section contains the following imports:

            KERNEL32.dll
                     0000000180001000 Import Address Table
                     0000000180002000 Import Name Table
                             0 GetProcAddress
            VCRUNTIME140.dll
                             0 memcpy
          Section contains the following delay load imports:

            pgvector.dll
                     0000000180003000 Import Address Table
                             0 vector_from_text
        """
        self.assertEqual(checker.parse_imports(output),
                         ["KERNEL32.dll", "VCRUNTIME140.dll", "pgvector.dll"])

    def test_rejects_unrecognized_or_empty_import_output(self):
        for output in ("mystery dumpbin format", "Section contains the following imports:\n  Summary\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                checker.parse_imports(output)

    def test_system_allowlist_is_narrow_and_documented(self):
        self.assertTrue(checker.is_system_dll("KERNEL32.dll"))
        self.assertTrue(checker.is_system_dll("api-ms-win-core-file-l1-2-0.dll"))
        self.assertTrue(checker.is_system_dll("api-ms-win-crt-runtime-l1-1-0.dll"))
        self.assertFalse(checker.is_system_dll("api-ms-win-security-base-l1-1-0.dll"))
        self.assertFalse(checker.is_system_dll("vendor_helper.dll"))


class PackageInspectionTests(unittest.TestCase):
    def test_resolves_package_import_and_rejects_unknown_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "bin" / "app.exe"
            dep = root / "lib" / "local.dll"
            app.parent.mkdir()
            dep.parent.mkdir()
            app.touch()
            dep.touch()
            dumpbin = root.parent / "dumpbin.exe"
            dumpbin.touch()
            header = "8664 machine (x64)\n20B magic # (PE32+)\n10.00 operating system version\n6.00 subsystem version\n"
            report = {"inspected_files": [], "files": []}
            def run(command, **kwargs):
                return subprocess.CompletedProcess(command, 0,
                    header if command[1] == "/headers" else
                    "Section contains the following imports:\n    local.dll\n    KERNEL32.dll\n", "")
            with patch.object(checker.subprocess, "run", side_effect=run):
                self.assertEqual(checker.inspect(root, dumpbin, report), 2)
            imports = report["files"][0]["imports"]
            self.assertEqual(imports[0]["resolution"], "package")
            self.assertEqual(imports[1]["resolution"], "windows-system-allowlist")

            def unknown(command, **kwargs):
                return subprocess.CompletedProcess(command, 0,
                    header if command[1] == "/headers" else
                    "Section contains the following imports:\n    unknown.dll\n", "")
            with patch.object(checker.subprocess, "run", side_effect=unknown):
                with self.assertRaisesRegex(ValueError, "unresolved non-system import"):
                    checker.inspect(root, dumpbin, {"inspected_files": [], "files": []})

    def test_archive_report_binds_names_and_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "core.tar.gz"
            archive.write_bytes(b"archive contents")
            self.assertEqual(checker.archive_evidence([archive]), [{
                "basename": "core.tar.gz",
                "sha256": hashlib.sha256(b"archive contents").hexdigest()}])

    def test_cli_writes_failed_report_if_tool_version_is_unrecognized(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dumpbin = root / "dumpbin.exe"
            dumpbin.touch()
            report_path = root / "report.json"
            argv = ["checker", str(root), "--dumpbin", str(dumpbin), "--report", str(report_path)]
            with patch.object(sys, "argv", argv), patch.object(
                checker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "unexpected", "")
            ):
                self.assertEqual(checker.main(), 1)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"], "failed")
            self.assertIn("cannot identify Visual Studio dumpbin version", report["findings"][0])


if __name__ == "__main__":
    unittest.main()
