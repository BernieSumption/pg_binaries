#!/usr/bin/env python3
"""Reject Linux archive binaries that load unbundled runtime libraries."""

import argparse
from pathlib import Path
import re
import subprocess
import sys


SYSTEM_LIBRARIES = {
    "libc.so.6", "libm.so.6", "libpthread.so.0", "libdl.so.2",
    "librt.so.1", "libresolv.so.2", "ld-linux-x86-64.so.2",
    "ld-linux-aarch64.so.1",
}
DEPENDENCY = re.compile(r"^\s*(\S+)\s+=>\s+(/\S+)")
LOADER = re.compile(r"^\s*(/\S+)\s+\(")


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


def check(prefix):
    prefix = Path(prefix).resolve(strict=True)
    loaders = list((prefix / "lib/glibc").glob("ld-linux*.so.*"))
    if len(loaders) > 1:
        raise ValueError(f"multiple bundled glibc loaders: {loaders}")
    loader = loaders[0] if loaders else None
    library_path = ":".join(str(prefix / relative) for relative in (
        "lib/glibc", "lib/runtime", "lib"
    ))
    count = 0
    for path in sorted(prefix.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        count += 1
        command = ([str(loader), "--library-path", library_path, "--list", str(path)]
                   if loader else ["ldd", str(path)])
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f"dependency check failed for {path}: {result.stderr.strip()}")
        try:
            for library, target in dependencies(result.stdout):
                resolved = target.resolve(strict=True)
                if resolved.is_relative_to(prefix):
                    continue
                if loader or library not in SYSTEM_LIBRARIES:
                    raise ValueError(f"unbundled dependency: {library} => {target}")
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
    if not count:
        raise ValueError(f"no ELF files found in {prefix}")
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path)
    args = parser.parse_args()
    try:
        count = check(args.prefix)
    except (OSError, ValueError) as exc:
        print(f"check_elf_dependencies: {exc}", file=sys.stderr)
        return 1
    print(f"Checked dependencies of {count} ELF files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
