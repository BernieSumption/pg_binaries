#!/usr/bin/env python3
"""Check Mach-O architecture, dependencies and deployment target in an installation."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SYSTEM_PREFIXES = ("/usr/lib/", "/System/Library/")


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, capture_output=True, text=True, check=False)


def minimum_os(target: str) -> tuple[int, ...]:
    import json

    support = json.loads((ROOT / "support.json").read_text(encoding="utf-8"))
    value = support["targets"][target]["minimum_os_version"]
    return tuple(int(part) for part in value.split("."))


def is_system(path: str) -> bool:
    return path.startswith(SYSTEM_PREFIXES)


def load_commands(output: str) -> list[tuple[str, str]]:
    commands: list[tuple[str, str]] = []
    command = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("cmd "):
            command = line[4:]
        elif command == "LC_ID_DYLIB":
            match = re.match(r"name (\S+)", line)
            if match:
                commands.append((command, match.group(1)))
        elif command == "LC_BUILD_VERSION":
            match = re.match(r"minos (\S+)", line)
            if match:
                commands.append((command, match.group(1)))
        elif command == "LC_VERSION_MIN_MACOSX":
            match = re.match(r"version (\S+)", line)
            if match:
                commands.append((command, match.group(1)))
        elif command == "LC_RPATH":
            match = re.match(r"path (\S+)", line)
            if match:
                commands.append((command, match.group(1)))
    return commands


def version(value: str) -> tuple[int, ...] | None:
    if not re.fullmatch(r"\d+(?:\.\d+){0,2}", value):
        return None
    parts = tuple(int(part) for part in value.split("."))
    return parts + (0,) * (3 - len(parts))


def inspect(installation: Path, target: str) -> tuple[int, int]:
    installation = installation.resolve()
    required_arch = target.removeprefix("macos-")
    required_minimum = version(".".join(map(str, minimum_os(target))))
    findings: list[str] = []
    inspected = 0

    for tool in ("file", "lipo", "otool"):
        if run("which", tool).returncode:
            findings.append(f"required macOS inspection tool is unavailable: {tool}")
    if findings:
        raise RuntimeError("\n".join(findings))

    for path in sorted(installation.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        file_result = run("file", "-b", str(path))
        if file_result.returncode:
            findings.append(f"file could not inspect {path.relative_to(installation)}")
            continue
        if "Mach-O" not in file_result.stdout:
            continue
        inspected += 1
        relative = path.relative_to(installation)

        archs = run("lipo", "-archs", str(path))
        if archs.returncode:
            findings.append(f"lipo could not inspect {relative}")
        elif required_arch not in archs.stdout.split():
            findings.append(f"{relative} lacks required architecture {required_arch}")

        linked = run("otool", "-L", str(path))
        loads = run("otool", "-l", str(path))
        if linked.returncode or loads.returncode:
            findings.append(f"otool could not inspect {relative}")
            continue
        dependencies = [
            line.strip().split(" (compatibility version", 1)[0]
            for line in linked.stdout.splitlines()[1:]
            if line.strip()
        ]
        commands = load_commands(loads.stdout)
        install_id = next((value for command, value in commands if command == "LC_ID_DYLIB"), None)
        for command, search_path in commands:
            if command != "LC_RPATH":
                continue
            if not search_path.startswith("@loader_path"):
                findings.append(f"{relative} has non-relative library search path {search_path}")
                continue
            suffix = search_path[len("@loader_path"):].lstrip("/")
            resolved = (path.parent / suffix).resolve()
            try:
                resolved.relative_to(installation)
            except ValueError:
                findings.append(f"{relative} has library search path outside installation: {search_path}")
        for dependency in dependencies:
            if dependency == install_id or is_system(dependency):
                continue
            if dependency.startswith("/"):
                findings.append(f"{relative} has non-system absolute dependency {dependency}")
            elif dependency.startswith("@loader_path"):
                suffix = dependency[len("@loader_path"):].lstrip("/")
                resolved = (path.parent / suffix).resolve()
                try:
                    resolved.relative_to(installation)
                except ValueError:
                    findings.append(f"{relative} has @loader_path dependency outside installation: {dependency}")
                else:
                    if not resolved.is_file():
                        findings.append(f"{relative} has unresolved @loader_path dependency {dependency}")
            else:
                findings.append(f"{relative} has unresolved dependency form {dependency}")

        minimum = next((value for command, value in commands
                        if command in ("LC_BUILD_VERSION", "LC_VERSION_MIN_MACOSX")), None)
        actual_minimum = version(minimum) if minimum else None
        if actual_minimum is None:
            findings.append(f"{relative} has no readable macOS deployment target")
        elif actual_minimum > required_minimum:
            findings.append(f"{relative} targets macOS {minimum}, above supported minimum {'.'.join(map(str, required_minimum))}")

    if not inspected:
        findings.append("no Mach-O files found")
    for finding in findings:
        print(f"FAIL: {finding}", file=sys.stderr)
    if not findings:
        print(f"Inspected {inspected} Mach-O files for {target}; no findings.")
    return inspected, len(findings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installation", type=Path, help="extracted postgresql/ directory")
    parser.add_argument("target", choices=("macos-arm64", "macos-x86_64"))
    arguments = parser.parse_args()
    if not arguments.installation.is_dir():
        parser.error(f"installation directory does not exist: {arguments.installation}")
    try:
        _, failures = inspect(arguments.installation, arguments.target)
    except (OSError, RuntimeError, KeyError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
