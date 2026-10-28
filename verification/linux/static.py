#!/usr/bin/env python3
"""Inspect ELF architecture, runtime dependencies and search paths in an installation."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys


MACHINES = {"linux-arm64": ("AArch64", "ld-linux-aarch64.so.1"),
            "linux-x86_64": ("Advanced Micro Devices X86-64", "ld-linux-x86-64.so.2")}


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, capture_output=True, text=True, check=False)


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def dynamic_entries(output: str, tag: str) -> list[str]:
    return re.findall(rf"\((?:{tag})\).*?\[(.*?)\]", output)


def inspect(installation: Path, target: str) -> tuple[int, int]:
    root = installation.resolve()
    machine, loader = MACHINES[target]
    findings: list[str] = []
    elfs: list[Path] = []
    for tool in ("file", "readelf"):
        if run("which", tool).returncode:
            findings.append(f"required Linux inspection tool is unavailable: {tool}")
    if findings:
        raise RuntimeError("\n".join(findings))

    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        result = run("file", "-b", str(path))
        if result.returncode:
            findings.append(f"file could not inspect {path.relative_to(root)}")
        elif "ELF" in result.stdout:
            elfs.append(path)

    bundled_loader = root / "lib" / "glibc" / loader
    if not bundled_loader.is_file():
        findings.append(f"bundled glibc interpreter is missing: lib/glibc/{loader}")

    for path in elfs:
        relative = path.relative_to(root)
        header = run("readelf", "-h", str(path))
        program = run("readelf", "-l", str(path))
        dynamic = run("readelf", "-d", str(path))
        if header.returncode or program.returncode or dynamic.returncode:
            findings.append(f"readelf could not inspect {relative}")
            continue
        if not re.search(rf"^\s*Machine:\s*{re.escape(machine)}\s*$", header.stdout, re.M):
            findings.append(f"{relative} is not target architecture {target} ({machine})")

        interpreter_match = re.search(r"Requesting program interpreter:\s*(.*?)\]", program.stdout)
        interpreter = interpreter_match.group(1) if interpreter_match else None
        if interpreter:
            if Path(interpreter).name != loader:
                findings.append(f"{relative} requests unexpected ELF interpreter {interpreter}")
        elif relative.parts[:1] == ("libexec",):
            findings.append(f"{relative} has no ELF interpreter; expected glibc payload")

        paths = dynamic_entries(dynamic.stdout, "RPATH|RUNPATH")
        search_dirs: list[Path] = []
        for entry in paths:
            for item in entry.split(":"):
                if not item:
                    findings.append(f"{relative} has an empty library search path")
                    continue
                if "$ORIGIN" not in item and "${ORIGIN}" not in item:
                    findings.append(f"{relative} has non-relative library search path {item}")
                    continue
                expanded = item.replace("${ORIGIN}", str(path.parent)).replace("$ORIGIN", str(path.parent))
                directory = Path(expanded)
                if not directory.is_absolute():
                    directory = path.parent / directory
                if not inside(directory, root):
                    findings.append(f"{relative} has library search path outside installation: {item}")
                    continue
                search_dirs.append(directory.resolve())
                if not directory.is_dir():
                    findings.append(f"{relative} has missing library search directory {item}")

        needed = dynamic_entries(dynamic.stdout, "NEEDED")
        for name in needed:
            if "/" in name:
                candidate = Path(name)
                if candidate.is_absolute() and inside(candidate, root) and candidate.is_file():
                    continue
                findings.append(f"{relative} has absolute or unresolved dependency {name}")
                continue
            candidates = [directory / name for directory in search_dirs]
            candidates += [root / "lib" / name, root / "lib" / "runtime" / name,
                           root / "lib" / "glibc" / name]
            if not any(candidate.is_file() and inside(candidate, root) for candidate in candidates):
                findings.append(f"{relative} has dependency outside installation or unresolved: {name}")

    if not elfs:
        findings.append("no ELF files found")
    for finding in findings:
        print(f"FAIL: {finding}", file=sys.stderr)
    if not findings:
        print(f"Inspected {len(elfs)} ELF files for {target}; no findings.")
    return len(elfs), len(findings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installation", type=Path, help="extracted postgresql/ directory")
    parser.add_argument("target", choices=tuple(MACHINES))
    arguments = parser.parse_args()
    if not arguments.installation.is_dir():
        parser.error(f"installation directory does not exist: {arguments.installation}")
    try:
        _, failures = inspect(arguments.installation, arguments.target)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
