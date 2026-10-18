#!/usr/bin/env python3
"""Stage vcpkg headers and import libraries for PostgreSQL 15's MSVC builder."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


DEPENDENCIES = {
    "icu": {
        "libraries": {"lib64/icuin.lib": ("icuin.lib",), "lib64/icuuc.lib": ("icuuc.lib",), "lib64/icudt.lib": ("icudt.lib",)},
        "dll_patterns": ("icu*.dll",),
    },
    "lz4": {"libraries": {"lib/liblz4.lib": ("liblz4.lib", "lz4.lib")}, "dll_patterns": ("*lz4*.dll",)},
    "zstd": {"libraries": {"lib/libzstd.lib": ("libzstd.lib", "zstd.lib")}, "dll_patterns": ("*zstd*.dll",)},
    "zlib": {"libraries": {"lib/zdll.lib": ("zdll.lib", "zlib.lib")}, "dll_patterns": ("zlib*.dll",)},
    "openssl": {
        "libraries": {"lib/libssl.lib": ("libssl.lib",), "lib/libcrypto.lib": ("libcrypto.lib",)},
        "dll_patterns": ("libssl*.dll", "libcrypto*.dll"),
    },
    "xml": {"libraries": {"lib/libxml2.lib": ("libxml2.lib",)}, "dll_patterns": ("libxml2*.dll",)},
    "xslt": {"libraries": {"lib/libxslt.lib": ("libxslt.lib",)}, "dll_patterns": ("libxslt*.dll",)},
}


def _hardlink_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
    if source.read_bytes() != target.read_bytes():
        raise RuntimeError(f"Staged library bytes differ from vcpkg input: {source}")


def _stage_headers(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"Missing vcpkg headers: {source}")
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        destination = target / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            _hardlink_or_copy(path, destination)


def stage(vcpkg_root: Path, staging_root: Path, config_path: Path) -> dict[str, str]:
    installed = vcpkg_root / "installed" / "x64-windows"
    if not (installed / "include").is_dir() or not (installed / "bin").is_dir():
        raise RuntimeError(f"Expected installed x64-windows vcpkg tree: {installed}")
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True)
    roots: dict[str, str] = {}

    for name, dependency in DEPENDENCIES.items():
        root = staging_root / name
        _stage_headers(installed / "include", root / "include")
        for relative_target, candidates in dependency["libraries"].items():
            source = next((installed / "lib" / item for item in candidates if (installed / "lib" / item).is_file()), None)
            if source is None:
                choices = ", ".join(candidates)
                raise RuntimeError(f"Missing {name} import library in {installed / 'lib'} (expected one of {choices})")
            _hardlink_or_copy(source, root / relative_target)
        roots[name] = root.resolve().as_posix().replace("'", "\\'")

    openssl_tools = (
        installed / "tools" / "openssl" / "openssl.exe",
        installed / "bin" / "openssl.exe",
    )
    openssl_exe = next((item for item in openssl_tools if item.is_file()), None)
    if openssl_exe is None:
        raise RuntimeError("Missing vcpkg OpenSSL CLI; install openssl[tools]:x64-windows")
    _hardlink_or_copy(openssl_exe, staging_root / "openssl" / "bin" / "openssl.exe")

    for name, dependency in DEPENDENCIES.items():
        for pattern in dependency["dll_patterns"]:
            if not list((installed / "bin").glob(pattern)):
                raise RuntimeError(f"Missing {name} runtime DLL matching {pattern} in {installed / 'bin'}")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        raise RuntimeError(f"Refusing to overwrite existing PostgreSQL MSVC configuration: {config_path}")
    config = "use strict;\nuse warnings;\nour $config = {\n"
    config += "  ldap => 0,\n  uuid => undef,\n  nls => undef,\n  perl => undef,\n  python => undef,\n  tcl => undef,\n"
    config += "".join(f"  {name} => '{root}',\n" for name, root in roots.items())
    config += "};\n1;\n"
    config_path.write_text(config, encoding="ascii")
    return roots


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vcpkg-root", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.vcpkg_root.resolve(), args.staging_root.resolve(), args.config.resolve()), sort_keys=True))


if __name__ == "__main__":
    main()
