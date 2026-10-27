#!/usr/bin/env python3
"""Bundle external Mach-O dependencies into a staged PostgreSQL tree."""

import hashlib
import os
import pathlib
import shutil
import subprocess
import sys


SYSTEM_PREFIXES = ("/usr/lib/", "/System/Library/")


def run(*args):
    return subprocess.run(args, capture_output=True, text=True)


def is_system(path):
    return path.startswith(SYSTEM_PREFIXES)


def dependencies(path):
    if run("lipo", "-archs", str(path)).returncode:
        return None
    result = run("otool", "-L", str(path))
    if result.returncode:
        return None
    found = [line.strip().split(" (compatibility version", 1)[0]
             for line in result.stdout.splitlines()[1:] if line.strip()]
    if path.suffix == ".dylib":
        identity = run("otool", "-D", str(path))
        if identity.returncode == 0 and len(identity.stdout.splitlines()) > 1:
            found = [dep for dep in found if dep != identity.stdout.splitlines()[-1].strip()]
    return found


def files(root):
    return (path for path in root.rglob("*")
            if path.is_file() and not path.is_symlink() and path.suffix != ".a")


def digest(path):
    return hashlib.sha256(path.read_bytes()).digest()


def inside(path, parent):
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def prefix_library(name, prefix):
    if not name or pathlib.PurePosixPath(name).name != name:
        return None
    for directory in ("lib", "lib64"):
        candidate = prefix / directory / name
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if resolved.is_file() and inside(resolved, prefix):
            return resolved
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        raise SystemExit("usage: bundle.py STAGED_POSTGRESQL_ROOT DEPENDENCY_PREFIX")
    root = pathlib.Path(argv[0]).resolve()
    prefix = pathlib.Path(argv[1]).resolve()
    if not root.is_dir() or not prefix.is_dir():
        raise SystemExit("staged root and dependency prefix must be directories")
    libdir = root / "lib"
    libdir.mkdir(parents=True, exist_ok=True)
    origins = {}

    def resolve(dep, binary):
        if dep.startswith("@loader_path/"):
            relative = dep.removeprefix("@loader_path/")
            candidate = (binary.parent / relative).resolve()
            if inside(candidate, root) and candidate.is_file():
                return candidate
            original = origins.get(binary)
            if original is not None:
                candidate = (original.parent / relative).resolve()
                if inside(candidate, prefix) and candidate.is_file():
                    return candidate
            return None
        if dep.startswith("@executable_path/"):
            raise SystemExit(f"unsupported executable-relative dependency: {binary}: {dep}")
        if dep.startswith("@rpath/"):
            name = dep.removeprefix("@rpath/")
            if pathlib.PurePosixPath(name).name != name:
                raise SystemExit(f"unsupported @rpath dependency: {binary}: {dep}")
            candidates = [libdir / name, prefix / "lib" / name, prefix / "lib64" / name]
        elif not dep.startswith("/"):
            source = prefix_library(dep, prefix)
            if source is not None:
                return source
            raise SystemExit(f"unsupported Mach-O dependency: {binary}: {dep}")
        elif dep.startswith("/"):
            path = pathlib.Path(dep)
            if inside(path, root) and path.is_file():
                return path.resolve()
            candidates = [libdir / path.name, path]
            # Installed dependency prefixes can relocate files under a different
            # absolute build path, so also resolve by basename in the explicit prefix.
            candidates.extend((prefix / "lib" / path.name, prefix / "lib64" / path.name))
        else:
            raise SystemExit(f"unsupported Mach-O dependency: {binary}: {dep}")
        for candidate in candidates:
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if resolved.is_file() and (inside(resolved, prefix) or inside(resolved, root)):
                return resolved
        return None

    # Re-scan after each pass so dependencies of newly copied dylibs are included.
    while True:
        changed = False
        for binary in list(files(root)):
            deps = dependencies(binary)
            if deps is None:
                continue
            for dep in deps:
                if is_system(dep):
                    continue
                source = resolve(dep, binary)
                if source is None:
                    raise SystemExit(f"unresolved Mach-O dependency: {binary}: {dep}")
                if inside(source, root):
                    continue
                target = libdir / source.name
                if target.exists():
                    if not target.is_file() or digest(target) != digest(source):
                        raise SystemExit(f"dependency filename collision: {target} and {source}")
                    continue
                shutil.copy2(source, target)
                origins[target] = source
                changed = True
        if not changed:
            break

    for binary in list(files(root)):
        deps = dependencies(binary)
        if deps is None:
            continue
        changed = False
        for dep in deps:
            if is_system(dep):
                continue
            source = resolve(dep, binary)
            if source is None:
                raise SystemExit(f"unresolved Mach-O dependency: {binary}: {dep}")
            target = source if inside(source, root) else libdir / source.name
            if not target.is_file():
                raise SystemExit(f"missing bundled dependency: {binary}: {dep}")
            replacement = "@loader_path/" + os.path.relpath(target, binary.parent)
            if dep != replacement:
                result = run("install_name_tool", "-change", dep, replacement, str(binary))
                if result.returncode:
                    raise SystemExit(result.stderr.strip() or f"install_name_tool failed: {binary}")
                changed = True
        if binary.suffix == ".dylib":
            current_id = run("otool", "-D", str(binary))
            expected_id = "@rpath/" + binary.name
            id_lines = current_id.stdout.splitlines()
            if current_id.returncode or not id_lines or id_lines[-1].strip() != expected_id:
                result = run("install_name_tool", "-id", expected_id, str(binary))
                if result.returncode:
                    raise SystemExit(result.stderr.strip() or f"install_name_tool failed: {binary}")
                changed = True
        if changed:
            result = run("codesign", "--force", "--sign", "-", str(binary))
            if result.returncode:
                raise SystemExit(result.stderr.strip() or f"codesign failed: {binary}")

    for binary in files(root):
        deps = dependencies(binary)
        if deps is None:
            continue
        for dep in deps:
            if is_system(dep):
                continue
            if not dep.startswith("@loader_path/"):
                raise SystemExit(f"non-relative dependency remains: {binary}: {dep}")
            target = (binary.parent / dep.removeprefix("@loader_path/")).resolve()
            if not inside(target, root) or not target.is_file():
                raise SystemExit(f"unresolved bundled dependency remains: {binary}: {dep}")


if __name__ == "__main__":
    main()
