#!/usr/bin/env python3
"""Record the native and data dependency evidence from the PostGIS trial."""

import json
import os
import pathlib
import re
import subprocess
import sys


root, output = map(pathlib.Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
brew = pathlib.Path(subprocess.check_output(["brew", "--prefix"], text=True).strip())
cellar = pathlib.Path(subprocess.check_output(["brew", "--cellar"], text=True).strip())
names = ("postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology")
share = root / "share/extension"


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def otool(path, option):
    return command("otool", option, str(path))


def module_files():
    modules = set()
    for name in names:
        control = (share / f"{name}.control").read_text()
        match = re.search(r"^\s*module_pathname\s*=\s*['\"]?\$libdir/([^'\"\s]+)", control, re.M)
        if match:
            modules.add(match.group(1))
        for sql in share.glob(f"{name}--*.sql"):
            modules.update(re.findall(r"\$libdir/([A-Za-z0-9_.-]+)", sql.read_text()))
    result = []
    for module in sorted(modules):
        candidates = [root / "lib" / (module + suffix) for suffix in ("", ".dylib", ".so")]
        found = [path for path in candidates if path.is_file()]
        if len(found) != 1:
            raise SystemExit(f"expected one installed module for $libdir/{module}, found {found}")
        result.extend(found)
    if not result:
        raise SystemExit("no native modules were found from the four installed SQL extension sets")
    return result


def rpaths(binary):
    lines = otool(binary, "-l").splitlines()
    found = []
    for index, line in enumerate(lines):
        if line.strip() == "cmd LC_RPATH":
            for entry in lines[index + 1:index + 5]:
                match = re.match(r"\s*path (.+?) \(offset \d+\)", entry)
                if match:
                    value = match.group(1).replace("@loader_path", str(binary.parent))
                    found.append(pathlib.Path(value))
                    break
    return found


def resolve(binary, dependency):
    candidates = []
    if dependency.startswith("/"):
        candidates.append(pathlib.Path(dependency))
    elif dependency.startswith("@loader_path/"):
        candidates.append(binary.parent / dependency.removeprefix("@loader_path/"))
    elif dependency.startswith("@rpath/"):
        suffix = dependency.removeprefix("@rpath/")
        for path in rpaths(binary):
            candidates.append(path / suffix)
        candidates.extend((brew / "lib" / suffix,))
        candidates.extend(cellar.glob(f"*/**/lib/{suffix}"))
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def dependencies(binary):
    lines = otool(binary, "-L").splitlines()[1:]
    return [line.strip().split(" ", 1)[0] for line in lines if line.strip()]


queue = list(module_files())
seen = {}
edges = []
while queue:
    binary = queue.pop(0).resolve()
    if str(binary) in seen:
        continue
    try:
        deps = dependencies(binary)
    except subprocess.CalledProcessError:
        continue
    seen[str(binary)] = binary
    for dependency in deps:
        if dependency.startswith(("/usr/lib/", "/System/Library/")):
            edges.append({"from": str(binary), "load_command": dependency, "kind": "system"})
            continue
        target = resolve(binary, dependency)
        edges.append({"from": str(binary), "load_command": dependency,
                      "resolved": str(target) if target else None,
                      "kind": "bundled-candidate" if target else "unresolved"})
        if target:
            queue.append(target)


formula_names = set()
for path in seen.values():
    try:
        relative = path.relative_to(cellar)
    except ValueError:
        continue
    if len(relative.parts) >= 2:
        formula_names.add(relative.parts[0])
formula_names.update(("geos", "proj", "gdal", "sfcgal", "json-c", "libxml2",
                      "protobuf-c", "pcre2"))

formula_output = command("brew", "list", "--formula", "--versions")
installed_versions = {}
for line in formula_output.splitlines():
    parts = line.split()
    if len(parts) >= 2 and parts[0] in formula_names:
        installed_versions[parts[0]] = parts[1:]

formulae = {}
if formula_names:
    info = json.loads(command("brew", "info", "--json=v2", *sorted(formula_names)))
    for item in info.get("formulae", []):
        name = item["name"]
        prefix = pathlib.Path(command("brew", "--prefix", name).strip())
        licence_files = sorted(
            str(path) for path in prefix.rglob("*")
            if path.is_file() and path.name.lower() in {"license", "license.txt", "copying", "copyright"}
            and len(path.relative_to(prefix).parts) <= 6
        )
        formulae[name] = {
            "installed_versions": installed_versions.get(name, []),
            "declared_license": item.get("license"),
            "source_urls": [item.get("urls", {}).get("stable", {}).get("url")],
            "formula_prefix": str(prefix),
            "formula_source": (item.get("tap") or "homebrew/core") + "/" + name,
            "licence_text_locations": licence_files,
        }


def data_tree(label, path):
    path = pathlib.Path(path)
    files = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else []
    return {"name": label, "path": str(path), "exists": path.is_dir(),
            "file_count": len(files),
            "files": [str(p.relative_to(path)) for p in files]}


proj_data = pathlib.Path(command("brew", "--prefix", "proj").strip()) / "share/proj"
gdal_data = pathlib.Path(command("gdal-config", "--datadir").strip())
record = {
    "schema_version": 1,
    "target": "PostGIS 3.6.4 / PostgreSQL 18.6 / macOS arm64",
    "modules": [str(path) for path in module_files()],
    "mach_o_dependency_edges": edges,
    "homebrew_formulae": formulae,
    "runtime_data_candidates": [data_tree("PROJ", proj_data), data_tree("GDAL", gdal_data)],
}
(output / "dependency-inventory.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
print(f"Recorded {len(record['modules'])} modules, {len(edges)} Mach-O dependency edges, "
      f"{len(formulae)} Homebrew formulae and runtime data candidates")
