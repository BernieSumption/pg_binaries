#!/usr/bin/env python3
"""Inspect Linux ELF architecture, loader paths and resolved library closure."""

import argparse
import json
from pathlib import Path
import re
import struct
import subprocess
import sys


SYSTEM_LIBRARIES = {
    "libc.so.6", "libm.so.6", "libpthread.so.0", "libdl.so.2",
    "librt.so.1", "libresolv.so.2",
    "ld-linux-x86-64.so.2", "ld-linux-aarch64.so.1",
}
DEPENDENCY = re.compile(r"^\s*(\S+)\s+=>\s+(/\S+)")
LOADER = re.compile(r"^\s*(/\S+)\s+\(")
MACHINES = {"Advanced Micro Devices X86-64": "x86_64", "AArch64": "arm64"}
INTERPRETERS = {
    "x86_64": {"/lib64/ld-linux-x86-64.so.2", "/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"},
    "arm64": {"/lib/ld-linux-aarch64.so.1", "/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1"},
}


def static_executable(path):
    with path.open("rb") as stream:
        header = stream.read(64)
        if len(header) < 64 or header[:6] != b"\x7fELF\x02\x01":
            return False
        if struct.unpack_from("<H", header, 16)[0] != 2:
            return False
        program_offset = struct.unpack_from("<Q", header, 32)[0]
        entry_size, entry_count = struct.unpack_from("<HH", header, 54)
        if entry_size < 4 or entry_count == 0:
            return False
        for index in range(entry_count):
            stream.seek(program_offset + index * entry_size)
            if struct.unpack("<I", stream.read(4))[0] == 3:
                return False
        return True


def dependencies(output):
    for line in output.splitlines():
        if "not found" in line:
            raise ValueError(line.strip())
        match = DEPENDENCY.match(line)
        if match:
            yield match.group(1), Path(match.group(2))
            continue
        match = LOADER.match(line)
        if match:
            path = Path(match.group(1))
            yield path.name, path


def inspect_elf(path):
    """Return architecture, interpreter and runtime search paths from readelf."""
    header = subprocess.run(["readelf", "-hW", str(path)], check=True,
                            capture_output=True, text=True).stdout
    machine_match = re.search(r"^\s*Machine:\s*(.+?)\s*$", header, re.M)
    if not machine_match or machine_match.group(1) not in MACHINES:
        raise ValueError(f"unsupported or unrecognized ELF machine in {path}")
    architecture = MACHINES[machine_match.group(1)]
    program = subprocess.run(["readelf", "-lW", str(path)], check=True,
                             capture_output=True, text=True).stdout
    interpreter_match = re.search(r"Requesting program interpreter:\s*([^]]+)\]", program)
    interpreter = interpreter_match.group(1).strip() if interpreter_match else None
    dynamic = subprocess.run(["readelf", "-dW", str(path)], check=True,
                             capture_output=True, text=True).stdout
    search_paths = []
    for line in dynamic.splitlines():
        match = re.search(r"\((?:RPATH|RUNPATH)\).*?\[([^]]*)\]", line)
        if match:
            search_paths.extend(match.group(1).split(":"))
    return architecture, interpreter, search_paths


def validate_paths(path, prefix, architecture, interpreter, search_paths):
    if interpreter:
        if interpreter not in INTERPRETERS[architecture]:
            raise ValueError(f"forbidden ELF interpreter {interpreter}")
        if not any(loader.name == Path(interpreter).name for loader in
                   (prefix / "lib/glibc").glob("ld-linux*.so.*")):
            raise ValueError(f"ELF interpreter has no bundled loader: {interpreter}")
    origin = path.resolve().parent
    for search_path in search_paths:
        if not search_path:
            raise ValueError(f"empty ELF runtime search path in {path}")
        if search_path != "$ORIGIN" and not search_path.startswith("$ORIGIN/"):
            raise ValueError(f"non-relocatable ELF runtime search path {search_path!r} in {path}")
        suffix = search_path[len("$ORIGIN"):].lstrip("/")
        resolved = (origin / suffix).resolve()
        if not resolved.is_relative_to(prefix):
            raise ValueError(f"ELF runtime search path escapes installation: {search_path!r} in {path}")


def check(prefix, expected_architecture=None, report=None):
    prefix = Path(prefix).resolve(strict=True)
    loaders = list((prefix / "lib/glibc").glob("ld-linux*.so.*"))
    if len(loaders) > 1:
        raise ValueError(f"multiple bundled glibc loaders: {loaders}")
    loader = loaders[0] if loaders else None
    architecture = expected_architecture
    if loader:
        loader_architecture, _, _ = inspect_elf(loader)
        if architecture and architecture != loader_architecture:
            raise ValueError(f"bundled loader architecture is {loader_architecture}, expected {architecture}")
        architecture = loader_architecture
    if architecture not in ("x86_64", "arm64"):
        raise ValueError("cannot determine architecture; provide --architecture or bundle a glibc loader")
    if report is not None:
        report["architecture"] = architecture
    library_path = ":".join(str(prefix / relative) for relative in (
        "lib/glibc", "lib", "lib/runtime"
    ))
    count = 0
    for path in sorted(prefix.rglob("*")):
        if path.is_symlink():
            try:
                target = path.resolve(strict=True)
            except OSError as exc:
                raise ValueError(f"broken installation symlink {path}: {exc}") from exc
            if not target.is_relative_to(prefix):
                raise ValueError(f"installation symlink escapes prefix: {path} -> {target}")
            continue
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        count += 1
        if report is not None:
            report["inspected_files"].append(path.relative_to(prefix).as_posix())
        try:
            file_architecture, interpreter, search_paths = inspect_elf(path)
            if report is not None:
                report["files"].append({
                    "path": path.relative_to(prefix).as_posix(),
                    "architecture": file_architecture,
                    "interpreter": interpreter,
                    "runtime_search_paths": search_paths,
                })
            if file_architecture != architecture:
                raise ValueError(f"ELF architecture is {file_architecture}; expected {architecture}")
            validate_paths(path, prefix, architecture, interpreter, search_paths)
            if static_executable(path):
                continue
            command = ([str(loader), "--library-path", library_path, "--list", str(path)]
                       if loader else ["ldd", str(path)])
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                raise ValueError(f"dependency check failed: {result.stderr.strip()}")
            for library, target in dependencies(result.stdout):
                resolved = target.resolve(strict=True)
                if resolved.is_relative_to(prefix):
                    continue
                if loader or library not in SYSTEM_LIBRARIES:
                    raise ValueError(f"unbundled dependency: {library} => {target}")
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            raise ValueError(f"{path}: {exc}") from exc
    if not count:
        raise ValueError(f"no ELF files found in {prefix}")
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"))
    parser.add_argument("--report", type=Path,
                        help="write JSON inspection evidence to this path")
    args = parser.parse_args()
    report = {
        "schema_version": 1,
        "architecture": args.architecture,
        "readelf_version": None,
        "inspected_files": [],
        "files": [],
        "outcome": "failed",
        "findings": [],
        "limits": [
            "Static ELF inspection does not find libraries loaded dynamically by application code.",
            "It does not inspect data-file access or absolute paths in non-runtime metadata.",
            "Dependency closure reflects the bundled loader --list result for the inspected files.",
        ],
    }
    try:
        version = subprocess.run(["readelf", "--version"], check=True,
                                  capture_output=True, text=True).stdout.splitlines()[0]
        report["readelf_version"] = version
        count = check(args.prefix, args.architecture, report)
        report["outcome"] = "passed"
        report["findings"].append(f"Inspected architecture and runtime paths for {count} ELF files.")
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        report["findings"].append(str(exc))
        if args.report:
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"check_elf_dependencies: {exc}", file=sys.stderr)
        return 1
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Checked architecture and dependencies of {count} ELF files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
