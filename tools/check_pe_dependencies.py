#!/usr/bin/env python3
"""Check Windows PE architecture, target headers, and imported DLL closure."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


SYSTEM_DLLS = {
    "advapi32.dll", "bcrypt.dll", "bcryptprimitives.dll", "cfgmgr32.dll",
    "combase.dll", "comctl32.dll", "comdlg32.dll", "crypt32.dll",
    "dnsapi.dll", "gdi32.dll", "gdi32full.dll", "imm32.dll", "iphlpapi.dll",
    "kernel32.dll", "kernelbase.dll", "msvcrt.dll", "mswsock.dll",
    "ncrypt.dll", "netapi32.dll", "normaliz.dll", "ntdll.dll", "ole32.dll",
    "oleaut32.dll", "powrprof.dll", "profapi.dll", "psapi.dll", "rpcrt4.dll",
    "secur32.dll", "setupapi.dll", "shell32.dll", "shlwapi.dll", "user32.dll",
    "userenv.dll", "usp10.dll", "uxtheme.dll", "version.dll", "winhttp.dll",
    "winmm.dll", "winspool.drv", "wldap32.dll", "ws2_32.dll", "wsock32.dll",
}
API_SET_PREFIXES = ("api-ms-win-core-", "api-ms-win-crt-",
                    "ext-ms-win-kernel32-", "ext-ms-win-ntuser-")
DLL_NAME = re.compile(r"^[A-Za-z0-9_.+-]+\.(?:dll|drv)$", re.I)
VERSION = re.compile(r"\b(\d+)\.(\d+)(?:\.(\d+))?\b")


class ImportSectionsMissing(ValueError):
    pass


def is_system_dll(name):
    lowered = name.lower()
    return lowered in SYSTEM_DLLS or (
        lowered.endswith(".dll") and any(lowered.startswith(prefix) for prefix in API_SET_PREFIXES)
    )


def parse_headers(output):
    """Read only the PE facts emitted in dumpbin /headers output; fail closed."""
    machine = re.search(r"^\s*8664\s+machine\s+\(x64\)\s*$", output, re.I | re.M)
    magic = re.search(r"^\s*20B\s+magic\s+#\s*\(PE32\+\)\s*$", output, re.I | re.M)
    if not machine or not magic:
        raise ValueError("unrecognized or unsupported PE machine/magic in dumpbin /headers")
    os_match = re.search(r"^\s*(\d+(?:\.\d+){1,2})\s+operating system version\s*$", output, re.I | re.M)
    subsystem_match = re.search(r"^\s*(\d+(?:\.\d+){1,2})\s+subsystem version\s*$", output, re.I | re.M)
    if not os_match or not subsystem_match:
        raise ValueError("dumpbin /headers did not expose both OS and subsystem version fields")
    os_version = tuple(map(int, os_match.group(1).split(".")))
    subsystem_version = tuple(map(int, subsystem_match.group(1).split(".")))
    if os_version[0] > 10 or (os_version[0] == 10 and os_version[1] > 0):
        raise ValueError(f"PE OS version {os_match.group(1)} exceeds Windows 10 floor")
    if subsystem_version[0] > 10 or (subsystem_version[0] == 10 and subsystem_version[1] > 0):
        raise ValueError(f"PE subsystem version {subsystem_match.group(1)} exceeds Windows 10 floor")
    return {"machine": "AMD64", "optional_header": "PE32+",
            "os_version": os_match.group(1), "subsystem_version": subsystem_match.group(1)}


def parse_import_details(output):
    """Parse DLL headings and named/ordinal imports from dumpbin output.

    Function rows are retained separately for normal and delay-load imports. A
    function identified only by ordinal is recorded as ``#<ordinal>``. Any
    heading-like DLL outside a recognized imports section is ambiguous.
    """
    imports, by_name, sections = [], {}, 0
    in_import_section = False
    current = None
    delay_section = False
    for line in output.splitlines():
        lowered = line.lower()
        heading = re.search(r"\bsection contains the following (delay load )?imports:\s*$", lowered)
        if heading:
            sections += 1
            in_import_section = True
            delay_section = bool(heading.group(1))
            current = None
            continue
        if in_import_section and line.strip().lower() == "summary":
            in_import_section = False
            current = None
            continue
        if in_import_section:
            if re.match(r"^\s{2,}[A-Za-z0-9_.+-]+\.(?:dll|drv)\s*$", line, re.I):
                name = line.strip()
                if not DLL_NAME.fullmatch(name):
                    raise ValueError(f"unrecognized import DLL name: {line.strip()}")
                key = name.lower()
                current = by_name.get(key)
                if current is None:
                    current = {"name": name, "functions": [], "delay_functions": []}
                    by_name[key] = current
                    imports.append(current)
                elif current["name"] != name:
                    raise ValueError(f"inconsistent DLL import spelling: {name}")
            elif line.strip() and not line[:1].isspace():
                in_import_section = False
                current = None
            elif current is not None:
                # dumpbin emits IAT/INT address rows as well as one function row
                # per import. Ignore the table labels and keep symbol rows only.
                ordinal_only = re.match(r"^\s*(?:0x)?([0-9]+)\s*$", line)
                if ordinal_only:
                    target = "delay_functions" if delay_section else "functions"
                    value = f"#{ordinal_only.group(1)}"
                    if value not in current[target]:
                        current[target].append(value)
                    continue
                match = re.match(
                    r"^\s*(?:(?:0x)?[0-9A-F]{8,16}\s+)?(?:(?:0x)?[0-9]+\s+)?(\S+)\s*$",
                    line, re.I)
                if match:
                    symbol = match.group(1)
                    if symbol.lower() not in {
                            "import", "address", "table", "name", "time", "date",
                            "stamp", "forwarder", "chain", "bound", "unload"}:
                        target = "delay_functions" if delay_section else "functions"
                        value = symbol
                        if value not in current[target]:
                            current[target].append(value)
    no_imports = re.search(r"\bno (?:normal |delay[- ]load )?imports?\b", output, re.I)
    if sections == 0 and not no_imports:
        raise ImportSectionsMissing("dumpbin /imports contains no recognized import sections")
    if sections == 0 and no_imports:
        return []
    if not imports and not no_imports:
        raise ValueError("recognized import sections contained no parseable DLL headings")
    return imports


def parse_imports(output):
    """Compatibility wrapper returning imported DLL names only."""
    return [entry["name"] for entry in parse_import_details(output)]


def pe_import_directories(path):
    """Return the PE32+ import and delay-import RVA/size pairs."""
    data = Path(path).read_bytes()

    def require(offset, size, what):
        if offset < 0 or size < 0 or offset + size > len(data):
            raise ValueError(f"truncated PE header while reading {what}")

    require(0, 64, "DOS header")
    if data[:2] != b"MZ":
        raise ValueError("invalid PE DOS signature")
    pe_offset = int.from_bytes(data[0x3C:0x40], "little")
    require(pe_offset, 24, "PE signature and COFF header")
    if data[pe_offset:pe_offset + 4] != b"PE\0\0":
        raise ValueError("invalid PE signature")
    coff = pe_offset + 4
    optional_size = int.from_bytes(data[coff + 16:coff + 18], "little")
    optional = coff + 20
    require(optional, optional_size, "optional header")
    if optional_size < 2 or int.from_bytes(data[optional:optional + 2], "little") != 0x20B:
        raise ValueError("PE optional header is not PE32+")
    number_offset = optional + 108
    require(number_offset, 4, "PE32+ data-directory count")
    number_of_directories = int.from_bytes(data[number_offset:number_offset + 4], "little")
    if number_of_directories < 14:
        raise ValueError("PE32+ optional header does not declare import and delay-import directories")
    directories = optional + 112
    if optional_size < 112 + 14 * 8:
        raise ValueError("truncated PE32+ optional-header data directories")
    require(directories, 14 * 8, "PE32+ import data directories")
    import_pair = tuple(int.from_bytes(data[directories + 8 + i * 4:directories + 12 + i * 4], "little")
                        for i in range(2))
    delay_offset = directories + 13 * 8
    delay_pair = tuple(int.from_bytes(data[delay_offset + i * 4:delay_offset + 4 + i * 4], "little")
                       for i in range(2))
    return import_pair, delay_pair


def archive_evidence(paths):
    entries, basenames = [], set()
    for supplied in paths:
        path = Path(supplied)
        if not path.is_file():
            raise ValueError(f"archive is missing or not a regular file: {path}")
        if path.name.lower() in basenames:
            raise ValueError(f"duplicate archive basename: {path.name}")
        basenames.add(path.name.lower())
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        entries.append({"basename": path.name, "sha256": digest.hexdigest()})
    return entries


def dumpbin_version(executable):
    result = subprocess.run([str(executable), "/?"], capture_output=True, text=True)
    text = result.stdout + "\n" + result.stderr
    match = re.search(r"Microsoft\s+\(R\)\s+COFF/PE Dumper\s+Version\s+([^\r\n]+)", text, re.I)
    if not match:
        raise ValueError("cannot identify Visual Studio dumpbin version from /? output")
    return match.group(1).strip()


def inspect(prefix, dumpbin, report):
    prefix = Path(prefix).resolve(strict=True)
    if not Path(dumpbin).is_file():
        raise ValueError(f"explicit dumpbin executable does not exist: {dumpbin}")
    by_name = {}
    for path in prefix.rglob("*"):
        if path.is_file() and path.suffix.lower() in (".exe", ".dll"):
            key = path.name.lower()
            if key in by_name:
                raise ValueError(f"case-insensitive PE basename collision: {path.name} and {by_name[key]}")
            by_name[key] = path
    if not by_name:
        raise ValueError("no .exe or .dll files found in assembled installation")
    report["inspected_files"] = []
    for path in sorted(by_name.values(), key=lambda p: p.as_posix().lower()):
        relative = path.relative_to(prefix).as_posix()
        report["inspected_files"].append(relative)
        def run(option):
            result = subprocess.run([str(dumpbin), option, str(path)], check=False,
                                    capture_output=True, text=True, errors="replace")
            if result.returncode:
                raise ValueError(f"dumpbin {option} failed for {relative}: {result.stderr.strip()}")
            return result.stdout
        header = parse_headers(run("/headers"))
        import_output = run("/imports")
        try:
            import_details = parse_import_details(import_output)
            imports = [entry["name"] for entry in import_details]
        except ImportSectionsMissing:
            import_directory, delay_directory = pe_import_directories(path)
            if import_directory != (0, 0) or delay_directory != (0, 0):
                raise
            import_details = []
            imports = []
        if not imports:
            import_directory, delay_directory = pe_import_directories(path)
            if import_directory != (0, 0) or delay_directory != (0, 0):
                raise ValueError(f"dumpbin listed no imports for PE file with import directories: {relative}")
        resolved = []
        detail_by_name = {entry["name"].lower(): entry for entry in import_details} if imports else {}
        for name in imports:
            candidate = by_name.get(name.lower())
            if candidate:
                resolution = {"name": name, "resolution": "package",
                              "path": candidate.relative_to(prefix).as_posix()}
            elif is_system_dll(name):
                resolution = {"name": name, "resolution": "windows-system-allowlist"}
            else:
                raise ValueError(f"unresolved non-system import {name} in {relative}")
            detail = detail_by_name[name.lower()]
            resolution["functions"] = detail["functions"]
            resolution["delay_functions"] = detail["delay_functions"]
            resolved.append(resolution)
        report["files"].append({"path": relative, **header, "imports": resolved})
    return len(by_name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path, help="assembled and relocated installation root")
    parser.add_argument("--dumpbin", required=True, type=Path,
                        help="explicit path to Visual Studio dumpbin.exe")
    parser.add_argument("--archive", type=Path, action="append", default=[],
                        help="final archive to bind into report (repeatable)")
    parser.add_argument("--report", type=Path, required=True, help="JSON report output path")
    args = parser.parse_args()
    report = {"schema_version": 1, "platform": "windows", "architecture": "x86_64",
              "minimum_os": "10.0.10240", "api_floor_status": "unresolved",
              "dumpbin_version": None, "archives": [],
              "inspected_files": [], "files": [], "findings": [], "outcome": "failed",
              "limits": [
                  "Imports loaded dynamically by application code and data-file accesses are not detected.",
                  "DLL resolution checks package basename closure and the stated Windows system allowlist; it does not emulate all Windows loader search-order rules.",
                  "PE OS and subsystem header versions do not encode the Windows 10 build number; the check enforces the 10.0 major/minor floor only.",
                  "API-set families allowed are api-ms-win-core, api-ms-win-crt, ext-ms-win-kernel32, and ext-ms-win-ntuser.",
                  "Imported function names are recorded for review but are not checked against Windows 10 build 10240 availability.",
              ]}
    try:
        report["archives"] = archive_evidence(args.archive)
        report["dumpbin_version"] = dumpbin_version(args.dumpbin)
        count = inspect(args.prefix, args.dumpbin, report)
        report["outcome"] = "passed"
        report["findings"].append(f"Inspected headers and imports for {count} PE files.")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        report["findings"].append(str(exc))
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"check_pe_dependencies: {exc}", file=sys.stderr)
        return 1
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Checked architecture and imports of {count} PE files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
