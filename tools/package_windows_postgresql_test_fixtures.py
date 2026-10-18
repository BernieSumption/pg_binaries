#!/usr/bin/env python3
"""Remove only installed SQL extension fixtures sourced from PostgreSQL tests."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def exclude_test_extensions(source_root: Path, install_root: Path) -> dict[str, object]:
    test_root = source_root / "src" / "test" / "modules"
    extension_root = install_root / "share" / "extension"
    contrib_root = source_root / "contrib"
    if not test_root.is_dir() or not extension_root.is_dir():
        raise RuntimeError("Expected PostgreSQL test-module source and installed extension directories")

    test_controls = sorted(test_root.rglob("*.control"))
    contrib_controls = {path.name for path in contrib_root.rglob("*.control")} if contrib_root.is_dir() else set()
    test_modules: set[str] = set()
    for makefile in sorted(test_root.rglob("Makefile")):
        contents = re.sub(r"\\\r?\n", " ", makefile.read_text(encoding="utf-8"))
        for key in ("MODULE_big", "MODULES"):
            for value in re.findall(rf"^{key}\s*=\s*(.+)$", contents, flags=re.MULTILINE):
                test_modules.update(value.split())

    def makefile_modules(root: Path) -> set[str]:
        names: set[str] = set()
        if not root.is_dir():
            return names
        for makefile in root.rglob("Makefile"):
            contents = re.sub(r"\\\r?\n", " ", makefile.read_text(encoding="utf-8"))
            for key in ("MODULE_big", "MODULES"):
                for value in re.findall(rf"^{key}\s*=\s*(.+)$", contents, flags=re.MULTILINE):
                    names.update(value.split())
        return names

    contrib_modules = makefile_modules(contrib_root)
    msvc_file = source_root / "src" / "tools" / "msvc" / "Mkvcbuild.pm"
    if not msvc_file.is_file():
        raise RuntimeError(f"Missing upstream MSVC project inventory: {msvc_file}")
    msvc_text = msvc_file.read_text(encoding="utf-8")
    core_modules = set(re.findall(r"AddProject\(\s*'([^']+)'\s*,\s*'dll'", msvc_text))
    conversion_makefile = source_root / "src" / "backend" / "utils" / "mb" / "conversion_procs" / "Makefile"
    if not conversion_makefile.is_file():
        raise RuntimeError(f"Missing upstream conversion-module inventory: {conversion_makefile}")
    conversion_text = re.sub(r"\\\r?\n", " ", conversion_makefile.read_text(encoding="utf-8"))
    conversion_match = re.search(r"^SUBDIRS\s*=\s*(.+)$", conversion_text, flags=re.MULTILINE)
    if not conversion_match:
        raise RuntimeError("Cannot identify PostgreSQL core conversion DLL project names")
    core_modules.update(conversion_match.group(1).split())
    core_modules.update(re.findall(r"AddTransformModule\(\s*'([^']+)'", msvc_text))
    collisions = sorted(test_modules & (contrib_modules | core_modules))
    if collisions:
        raise RuntimeError(f"Test-module DLL collides with ordinary PostgreSQL output: {', '.join(collisions)}")
    lib_root = install_root / "lib"
    if not lib_root.is_dir():
        raise RuntimeError("Expected installed PostgreSQL library directory")
    missing_dlls = sorted(name for name in test_modules if not (lib_root / f"{name}.dll").is_file())
    if missing_dlls:
        raise RuntimeError(f"Expected test-module DLLs are missing from PostgreSQL install: {', '.join(missing_dlls)}")

    candidates: list[tuple[str, list[Path]]] = []
    seen_names: set[str] = set()
    for control in test_controls:
        name = control.stem
        if name in seen_names:
            raise RuntimeError(f"Duplicate test-module extension name: {name}")
        seen_names.add(name)
        installed_control = extension_root / control.name
        if not installed_control.is_file():
            continue
        if control.name in contrib_controls:
            raise RuntimeError(f"Test extension collides with ordinary contrib extension: {control.name}")
        files = [installed_control, *sorted(extension_root.glob(f"{name}--*.sql"))]
        plain_sql = extension_root / f"{name}.sql"
        if plain_sql.is_file():
            files.append(plain_sql)
        candidates.append((name, files))

    if not candidates:
        raise RuntimeError("No installed PostgreSQL test-module SQL extensions matched the pinned source tree")
    native_files = sorted(lib_root / f"{name}.dll" for name in test_modules)
    excluded = sorted(
        [path.relative_to(install_root).as_posix() for _, files in candidates for path in files]
        + [path.relative_to(install_root).as_posix() for path in native_files]
    )
    for _, files in candidates:
        for path in files:
            path.unlink()
    for path in native_files:
        path.unlink()
    return {
        "source": "src/test/modules",
        "extension_names": [name for name, _ in candidates],
        "native_modules": sorted(test_modules),
        "excluded_files": excluded,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = exclude_test_extensions(args.source_root, args.install_root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
