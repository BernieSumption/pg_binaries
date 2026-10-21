#!/usr/bin/env python3
"""Report unresolved DLLs and imported names for a Windows PE dependency tree."""

import argparse
import json
import re
import subprocess
from pathlib import Path


SYSTEM_DLLS = {
    "advapi32.dll", "bcrypt.dll", "bcryptprimitives.dll", "cfgmgr32.dll",
    "clbcatq.dll", "combase.dll", "comctl32.dll", "comdlg32.dll", "crypt32.dll",
    "cryptbase.dll", "dbghelp.dll", "dnsapi.dll", "dwrite.dll", "dwmapi.dll",
    "gdi32.dll", "gdi32full.dll",
    "imm32.dll", "iphlpapi.dll", "kernel32.dll", "kernelbase.dll", "mpr.dll",
    "msvcp_win.dll", "msvcrt.dll", "mswsock.dll", "netapi32.dll", "ncrypt.dll",
    "ntdll.dll", "odbc32.dll", "odbccp32.dll", "ole32.dll", "oleacc.dll", "oleaut32.dll", "powrprof.dll",
    "profapi.dll", "psapi.dll", "rpcrt4.dll", "secur32.dll", "setupapi.dll",
    "shell32.dll", "shcore.dll", "shlwapi.dll", "uxtheme.dll", "user32.dll",
    "userenv.dll", "version.dll", "winmm.dll", "winspool.drv", "wintrust.dll",
    "winhttp.dll", "wininet.dll", "wldap32.dll", "ws2_32.dll", "wtsapi32.dll",
    "xmllite.dll", "usp10.dll",
}
SYSTEM_PREFIXES = ("api-ms-win-", "ext-ms-win-")
IMPORT_NAME = re.compile(r"^\s*[0-9a-fA-F]+\s+<none>\s+[0-9a-fA-F]+\s+(\S+)\s*$")
EXPORT_NAME = re.compile(r"^\s*\[\s*\d+\s*\]\s+\+base\[\s*\d+\s*\]\s+[0-9a-fA-F]+\s+(\S+)\s*$")
DLL_NAME = re.compile(r"^\s*DLL Name:\s*(\S+)\s*$")
MAX_FINDINGS = 1000
MAX_ERRORS = 100


def parse_imports(output: str) -> list[tuple[str, str]]:
    section = output.split("The Import Tables", 1)
    if len(section) != 2:
        return []
    section = section[1].split("The Export Tables", 1)[0]
    imports: list[tuple[str, str]] = []
    dll = None
    for line in section.splitlines():
        match = DLL_NAME.match(line)
        if match:
            dll = match.group(1)
        elif dll:
            match = IMPORT_NAME.match(line)
            if match:
                imports.append((dll, match.group(1)))
    return imports


def parse_exports(output: str) -> set[str]:
    section = output.split("[Ordinal/Name Pointer] Table", 1)
    if len(section) != 2:
        return set()
    exports: set[str] = set()
    for line in section[1].splitlines():
        match = EXPORT_NAME.match(line)
        if match:
            exports.add(match.group(1))
    return exports


def is_system_dll(name: str) -> bool:
    folded = name.casefold()
    return folded in SYSTEM_DLLS or folded.startswith(SYSTEM_PREFIXES)


def file_index(directories: list[Path]) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for directory in directories:
        try:
            entries = directory.iterdir()
        except OSError:
            continue
        for entry in entries:
            if entry.is_file() and entry.suffix.casefold() in {".dll", ".exe"}:
                index.setdefault(entry.name.casefold(), entry.resolve())
    return index


def diagnose(root: Path, directories: list[Path], objdump: str) -> dict:
    available = file_index(directories)
    pending = [root.resolve()]
    scanned: set[Path] = set()
    inspected: dict[Path, tuple[list[tuple[str, str]], set[str]]] = {}
    unresolved_dlls = []
    missing_symbols = []
    objdump_errors = []
    while pending:
        module = pending.pop()
        if module in scanned:
            continue
        scanned.add(module)
        if module not in inspected:
            try:
                result = subprocess.run(
                    [objdump, "-p", str(module)], check=True, capture_output=True,
                    text=True, errors="replace",
                )
                inspected[module] = (parse_imports(result.stdout), parse_exports(result.stdout))
            except (OSError, subprocess.CalledProcessError) as error:
                detail = getattr(error, "stderr", "") or str(error)
                if len(objdump_errors) < MAX_ERRORS:
                    objdump_errors.append({"file": str(module), "error": detail[-1000:]})
                continue
        imports, _ = inspected[module]
        for dll_name in dict.fromkeys(dll for dll, _ in imports):
            dependency = available.get(dll_name.casefold())
            if dependency is None:
                if not is_system_dll(dll_name) and len(unresolved_dlls) < MAX_FINDINGS:
                    unresolved_dlls.append({"importer": str(module), "dll": dll_name})
                continue
            pending.append(dependency)
            if dependency not in inspected:
                try:
                    dependency_result = subprocess.run(
                        [objdump, "-p", str(dependency)], check=True, capture_output=True,
                        text=True, errors="replace",
                    )
                    inspected[dependency] = (
                        parse_imports(dependency_result.stdout),
                        parse_exports(dependency_result.stdout),
                    )
                except (OSError, subprocess.CalledProcessError) as error:
                    detail = getattr(error, "stderr", "") or str(error)
                    if len(objdump_errors) < MAX_ERRORS:
                        objdump_errors.append({"file": str(dependency), "error": detail[-1000:]})
                    continue
            _, exports = inspected[dependency]
            for imported_dll, symbol in imports:
                if (imported_dll.casefold() == dll_name.casefold() and symbol not in exports
                        and len(missing_symbols) < MAX_FINDINGS):
                    missing_symbols.append({
                        "importer": str(module), "dll": dll_name, "symbol": symbol,
                    })
    return {
        "schema_version": 1,
        "root": str(root.resolve()),
        "search_directories": [str(path.resolve()) for path in directories],
        "scanned_modules": len(scanned),
        "resolved_modules": [str(path) for path in sorted(scanned)],
        "unresolved_dlls": sorted(unresolved_dlls, key=lambda item: (item["importer"], item["dll"].casefold())),
        "missing_symbols": sorted(missing_symbols, key=lambda item: (item["importer"], item["dll"].casefold(), item["symbol"].casefold())),
        "findings_truncated": len(unresolved_dlls) == MAX_FINDINGS or len(missing_symbols) == MAX_FINDINGS,
        "errors_truncated": len(objdump_errors) == MAX_ERRORS,
        "objdump_errors": sorted(objdump_errors, key=lambda item: item["file"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--search-directory", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--modules-output", type=Path)
    parser.add_argument("--objdump", default="objdump")
    args = parser.parse_args()
    result = diagnose(args.root, args.search_directory, args.objdump)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.modules_output:
        args.modules_output.parent.mkdir(parents=True, exist_ok=True)
        args.modules_output.write_text(
            json.dumps(result["resolved_modules"], indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        "PE import diagnostic: "
        f"{result['scanned_modules']} modules, "
        f"{len(result['missing_symbols'])} missing symbols, "
        f"{len(result['unresolved_dlls'])} unresolved DLLs, "
        f"{len(result['objdump_errors'])} objdump errors"
    )


if __name__ == "__main__":
    main()
