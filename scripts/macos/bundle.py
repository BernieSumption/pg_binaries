#!/usr/bin/env python3
"""Copy non-OS Mach-O dependencies and make a staged tree movable."""

import os
import json
import hashlib
import pathlib
import shutil
import subprocess
import sys


root = pathlib.Path(sys.argv[1]).resolve()
libdir = root / "lib"
libdir.mkdir(parents=True, exist_ok=True)
external_sources = {}


def run(*args):
    return subprocess.run(args, text=True, capture_output=True)


def macho_dependencies(path):
    result = run("otool", "-L", str(path))
    if result.returncode:
        return None
    return [line.strip().split(" ", 1)[0] for line in result.stdout.splitlines()[1:] if line.strip()]


def is_system(path):
    return path.startswith(("/usr/lib/", "/System/Library/"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).digest()


def files():
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink() and path.suffix != ".a":
            yield path


def resolve_dependency(dep):
    if dep.startswith("/"):
        return pathlib.Path(dep)
    if dep.startswith("@rpath/"):
        name = dep.removeprefix("@rpath/")
        candidates = [libdir / name]
        for prefix in ("/usr/local/opt", "/opt/homebrew/opt"):
            candidates.extend(pathlib.Path(prefix).glob("*/lib/" + name))
        for candidate in candidates:
            if candidate.exists():
                return candidate
    return None


# Grow the tree until dependencies of copied libraries have also been copied.
while True:
    changed = False
    for binary in list(files()):
        deps = macho_dependencies(binary)
        if deps is None:
            continue
        for dep in deps:
            if is_system(dep) or dep.startswith("@loader_path/") or dep.startswith("@executable_path/"):
                continue
            source = resolve_dependency(dep)
            if source is None or not source.exists():
                raise SystemExit(f"unresolved Mach-O dependency: {binary}: {dep}")
            target = libdir / source.name
            if source.resolve().is_relative_to(root):
                continue
            external_sources[source.name] = str(source.resolve())
            if not target.exists():
                shutil.copy2(source.resolve(), target)
                changed = True
            elif digest(target) != digest(source.resolve()):
                raise SystemExit(f"dependency filename collision: {target} and {source}")
    if not changed:
        break

for binary in files():
    deps = macho_dependencies(binary)
    if deps is None:
        continue
    relative_lib = os.path.relpath(libdir, binary.parent)
    loader_lib = "@loader_path" if relative_lib == "." else "@loader_path/" + relative_lib
    for dep in deps:
        if is_system(dep) or dep.startswith("@loader_path/") or dep.startswith("@executable_path/"):
            continue
        source = resolve_dependency(dep)
        if source is None:
            raise SystemExit(f"unresolved Mach-O dependency: {binary}: {dep}")
        target = libdir / source.name
        if not target.exists():
            raise SystemExit(f"missing bundled dependency: {binary}: {dep}")
        replacement = loader_lib + "/" + source.name
        if dep != replacement:
            subprocess.run(["install_name_tool", "-change", dep, replacement, str(binary)], check=True)
    if binary.suffix == ".dylib":
        subprocess.run(["install_name_tool", "-id", "@rpath/" + binary.name, str(binary)], check=True)
    # install_name_tool changes signed load commands; ad-hoc sign the final bytes.
    subprocess.run(["codesign", "--force", "--sign", "-", str(binary)], check=True)

# The runner's library search path must never hide an unbundled dependency.
for binary in files():
    deps = macho_dependencies(binary)
    if deps is None:
        continue
    for dep in deps:
        if dep.startswith("/") and not is_system(dep):
            raise SystemExit(f"non-system absolute dependency remains: {binary}: {dep}")
(root / "bundled-dependencies.json").write_text(json.dumps(external_sources, indent=2, sort_keys=True) + "\n")
print(f"Bundled Mach-O dependencies in {root}: {len(external_sources)} external libraries")
