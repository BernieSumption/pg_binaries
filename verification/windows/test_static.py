import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from verification.windows import static as checker


def make_pe32_plus(import_pair=(0, 0), delay_pair=(0, 0)):
    data = bytearray(400)
    data[:2] = b"MZ"
    data[0x3C:0x40] = (64).to_bytes(4, "little")
    data[64:68] = b"PE\0\0"
    data[68 + 16:68 + 18] = (240).to_bytes(2, "little")
    optional = 88
    data[optional:optional + 2] = (0x20B).to_bytes(2, "little")
    data[optional + 108:optional + 112] = (14).to_bytes(4, "little")
    for index, value in enumerate(import_pair):
        start = optional + 112 + 8 + index * 4
        data[start:start + 4] = value.to_bytes(4, "little")
    for index, value in enumerate(delay_pair):
        start = optional + 112 + 13 * 8 + index * 4
        data[start:start + 4] = value.to_bytes(4, "little")
    return data


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
        details = checker.parse_import_details(output)
        self.assertEqual(details, [
            {"name": "KERNEL32.dll", "functions": ["GetProcAddress"], "delay_functions": []},
            {"name": "VCRUNTIME140.dll", "functions": ["memcpy"], "delay_functions": []},
            {"name": "pgvector.dll", "functions": [], "delay_functions": ["vector_from_text"]},
        ])

    def test_records_address_prefixed_and_ordinal_only_imports(self):
        output = """
          Section contains the following imports:
            kernel32.dll
                     0000000180001000 Import Address Table
                     0000000180002000 Import Name Table
                     0000000000000000     0 GetProcAddress
                     0000000180003000     #17
        """
        self.assertEqual(checker.parse_import_details(output), [{
            "name": "kernel32.dll", "functions": ["GetProcAddress", "#17"],
            "delay_functions": []}])

    def test_merges_case_variants_of_the_same_windows_dll(self):
        output = """
          Section contains the following imports:
            KERNEL32.dll
                 0 GetProcAddress
          Section contains the following delay load imports:
            kernel32.dll
                 0 Sleep
        """
        self.assertEqual(checker.parse_import_details(output), [{
            "name": "KERNEL32.dll", "functions": ["GetProcAddress"],
            "delay_functions": ["Sleep"]}])

    def test_stops_at_dumpbin_section_summary(self):
        output = """
          Section contains the following imports:
            KERNEL32.dll
                 0 GetProcAddress
          Summary
                 1000 .data
                 2000 .rdata
                 3000 .text
        """
        self.assertEqual(checker.parse_import_details(output), [{
            "name": "KERNEL32.dll", "functions": ["GetProcAddress"],
            "delay_functions": []}])

    def test_rejects_unrecognized_or_empty_import_output(self):
        for output in ("mystery dumpbin format", "Section contains the following imports:\n  Summary\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                checker.parse_imports(output)

    def test_reads_zero_import_directories_from_pe32_plus(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "empty.dll"
            path.write_bytes(make_pe32_plus())
            self.assertEqual(checker.pe_import_directories(path), ((0, 0), (0, 0)))

    def test_reads_nonzero_import_directories_from_pe32_plus(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "imports.dll"
            path.write_bytes(make_pe32_plus(import_pair=(0x1000, 40), delay_pair=(0x2000, 32)))
            self.assertEqual(checker.pe_import_directories(path), ((0x1000, 40), (0x2000, 32)))

    def test_rejects_truncated_pe_optional_header(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "truncated.dll"
            path.write_bytes(make_pe32_plus()[:200])
            with self.assertRaisesRegex(ValueError, "truncated PE header"):
                checker.pe_import_directories(path)

            declared_short = make_pe32_plus()
            declared_short[68 + 16:68 + 18] = (216).to_bytes(2, "little")
            path.write_bytes(declared_short)
            with self.assertRaisesRegex(ValueError, "truncated PE32\+ optional-header"):
                checker.pe_import_directories(path)

    def test_system_allowlist_is_narrow_and_documented(self):
        self.assertTrue(checker.is_system_dll("KERNEL32.dll"))
        self.assertTrue(checker.is_system_dll("WLDAP32.dll"))
        self.assertTrue(checker.is_system_dll("XmlLite.dll"))
        self.assertTrue(checker.is_system_dll("DWrite.dll"))
        self.assertTrue(checker.is_system_dll("ODBC32.dll"))
        self.assertTrue(checker.is_system_dll("ODBCCP32.dll"))
        self.assertTrue(checker.is_system_dll("api-ms-win-core-file-l1-2-0.dll"))
        self.assertTrue(checker.is_system_dll("api-ms-win-crt-runtime-l1-1-0.dll"))
        self.assertFalse(checker.is_system_dll("api-ms-win-security-base-l1-1-0.dll"))
        self.assertFalse(checker.is_system_dll("vendor_helper.dll"))


class PackageInspectionTests(unittest.TestCase):
    def test_inspects_byte_identical_duplicate_basename_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "bin" / "app.exe"
            first = root / "bin" / "libecpg.dll"
            second = root / "lib" / "libecpg.dll"
            app.parent.mkdir()
            first.parent.mkdir(exist_ok=True)
            second.parent.mkdir()
            app.write_bytes(make_pe32_plus())
            first.write_bytes(make_pe32_plus())
            second.write_bytes(make_pe32_plus())
            dumpbin = root.parent / "dumpbin.exe"
            dumpbin.touch()
            header = "8664 machine (x64)\n20B magic # (PE32+)\n10.00 operating system version\n6.00 subsystem version\n"

            def run(command, **kwargs):
                return subprocess.CompletedProcess(command, 0,
                    header if command[1] == "/headers" else
                    ("Section contains the following imports:\n    libecpg.dll\n      0 ecpg_connect\n"
                     if Path(command[-1]).name == "app.exe" else "no imports"), "")

            report = {"inspected_files": [], "files": []}
            with patch.object(checker.subprocess, "run", side_effect=run):
                self.assertEqual(checker.inspect(root, dumpbin, report), 3)
            self.assertEqual(report["inspected_files"], [
                "bin/app.exe", "bin/libecpg.dll", "lib/libecpg.dll"])
            self.assertEqual([item["path"] for item in report["files"]], report["inspected_files"])
            self.assertEqual(report["files"][0]["imports"][0]["path"], "bin/libecpg.dll")

    def test_rejects_different_contents_for_duplicate_basename_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "bin" / "libecpg.dll"
            second = root / "lib" / "libecpg.dll"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_bytes(make_pe32_plus())
            second.write_bytes(make_pe32_plus() + b"different")
            dumpbin = root.parent / "dumpbin.exe"
            dumpbin.touch()
            with self.assertRaisesRegex(ValueError, "basename collision with different contents"):
                checker.inspect(root, dumpbin, {"inspected_files": [], "files": []})

    def test_unknown_import_output_requires_zero_import_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "app.exe"
            app.write_bytes(make_pe32_plus())
            dumpbin = root.parent / "dumpbin.exe"
            dumpbin.touch()
            header = "8664 machine (x64)\n20B magic # (PE32+)\n10.00 operating system version\n6.00 subsystem version\n"

            def run(command, **kwargs):
                return subprocess.CompletedProcess(command, 0,
                    header if command[1] == "/headers" else "unrecognized imports output", "")

            with patch.object(checker.subprocess, "run", side_effect=run):
                report = {"inspected_files": [], "files": []}
                self.assertEqual(checker.inspect(root, dumpbin, report), 1)
                self.assertEqual(report["files"][0]["imports"], [])

                app.write_bytes(make_pe32_plus(import_pair=(0x1000, 40)))
                with self.assertRaisesRegex(ValueError, "no recognized import sections"):
                    checker.inspect(root, dumpbin, {"inspected_files": [], "files": []})

                def explicit_no_imports(command, **kwargs):
                    return subprocess.CompletedProcess(command, 0,
                        header if command[1] == "/headers" else "no imports", "")
                with patch.object(checker.subprocess, "run", side_effect=explicit_no_imports):
                    with self.assertRaisesRegex(ValueError, "listed no imports"):
                        checker.inspect(root, dumpbin, {"inspected_files": [], "files": []})

                app.write_bytes(make_pe32_plus()[:200])
                with self.assertRaisesRegex(ValueError, "truncated PE header"):
                    checker.inspect(root, dumpbin, {"inspected_files": [], "files": []})

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
                    "Section contains the following imports:\n    local.dll\n      0 local_func\n    KERNEL32.dll\n      0 GetProcAddress\n"
                    "Section contains the following delay load imports:\n    KERNEL32.dll\n      0 Sleep\n", "")
            with patch.object(checker.subprocess, "run", side_effect=run):
                self.assertEqual(checker.inspect(root, dumpbin, report), 2)
            imports = report["files"][0]["imports"]
            self.assertEqual(imports[0]["resolution"], "package")
            self.assertEqual(imports[0]["functions"], ["local_func"])
            self.assertEqual(imports[1]["resolution"], "windows-system-allowlist")
            self.assertEqual(imports[1]["functions"], ["GetProcAddress"])
            self.assertEqual(imports[1]["delay_functions"], ["Sleep"])

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
            self.assertEqual(report["api_floor_status"], "unresolved")
            self.assertTrue(any("not checked against Windows 10 build 10240" in limit
                                for limit in report["limits"]))
            self.assertIn("cannot identify Visual Studio dumpbin version", report["findings"][0])


if __name__ == "__main__":
    unittest.main()
