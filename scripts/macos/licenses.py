#!/usr/bin/env python3
"""Collect licence texts for libraries embedded in a pilot archive."""

import json
import pathlib
import re
import shutil
import sys
import urllib.request


if len(sys.argv) not in (2, 3):
    raise SystemExit("usage: licenses.py <package-root> [source-dependencies.json]")

root = pathlib.Path(sys.argv[1]).resolve()
licenses = root / "LICENSES"
licenses.mkdir(exist_ok=True)
sources = json.loads((root / "bundled-dependencies.json").read_text())
formulas = {}
source_manifest = None
source_prefix = None
source_components = {}
source_libraries = {}

if len(sys.argv) == 3:
    manifest_path = pathlib.Path(sys.argv[2]).resolve()
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read source dependency manifest {manifest_path}: {exc}") from exc
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("components"), list):
        raise SystemExit("source dependency manifest must have schema_version 1 and a components list")
    # The agreed manifest location is <prefix>/share/pg_binaries/source-dependencies.json.
    if manifest_path.parent.name != "pg_binaries" or manifest_path.parent.parent.name != "share":
        raise SystemExit("source dependency manifest must be at <prefix>/share/pg_binaries/source-dependencies.json")
    source_manifest = manifest_path
    source_prefix = manifest_path.parent.parent.parent.resolve()
    for entry in manifest["components"]:
        if not isinstance(entry, dict):
            raise SystemExit("source dependency manifest components must be objects")
        package = entry.get("package")
        version = entry.get("version")
        libraries = entry.get("libraries")
        license_file = entry.get("license_file")
        license_source = entry.get("license_source")
        source_url = entry.get("source_url")
        source_sha256 = entry.get("source_sha256")
        if not all(isinstance(value, str) and value.strip() for value in
                   (package, version, license_file, license_source, source_url, source_sha256)):
            raise SystemExit("source dependency entries require package, version, license_file, license_source, source_url and source_sha256")
        if not isinstance(libraries, list) or not libraries or any(
            not isinstance(library, str) or not library or pathlib.Path(library).name != library
            for library in libraries
        ):
            raise SystemExit(f"source dependency {package} {version} requires library basenames")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256):
            raise SystemExit(f"source dependency {package} {version} has invalid source_sha256")
        license_path = (manifest_path.parent / license_file).resolve()
        if not license_path.is_relative_to(manifest_path.parent) or not license_path.is_file() or license_path.stat().st_size == 0:
            raise SystemExit(f"missing or unsafe licence text for source dependency {package} {version}: {license_file}")
        key = (package, version)
        if key in source_components:
            raise SystemExit(f"duplicate source dependency {package} {version}")
        component = dict(entry, _license_path=license_path)
        source_components[key] = component
        for library in libraries:
            if library in source_libraries:
                raise SystemExit(f"source library {library} is declared by multiple packages")
            source_libraries[library] = component

for library, source in sources.items():
    parts = pathlib.Path(source).parts
    if "Cellar" in parts:
        index = parts.index("Cellar")
        if len(parts) <= index + 2:
            raise SystemExit(f"cannot identify Homebrew package and version owning {source}")
        name, version = parts[index + 1 : index + 3]
        if (name, version) in source_components:
            raise SystemExit(f"dependency {name} {version} is present from both source archives and Homebrew")
        formulas.setdefault(("homebrew", name, version), []).append(library)
        continue
    if source_manifest is None:
        raise SystemExit(f"cannot identify package owning non-Homebrew dependency {source}; provide a source dependency manifest")
    if not pathlib.Path(source).is_absolute():
        raise SystemExit(f"source dependency path must be absolute: {source}")
    source_path = pathlib.Path(source).resolve()
    if not source_path.is_relative_to(source_prefix):
        raise SystemExit(f"source dependency path is outside its declared prefix: {source}")
    if not source_path.is_file():
        raise SystemExit(f"source dependency library is missing: {source}")
    component = source_libraries.get(pathlib.Path(source).name)
    if component is None:
        raise SystemExit(f"source dependency manifest has no package/version for library {pathlib.Path(source).name}")
    if pathlib.Path(source).name not in component["libraries"]:
        raise SystemExit(f"source dependency manifest does not map library {pathlib.Path(source).name}")
    package_key = (component["package"], component["version"])
    if ("homebrew", *package_key) in formulas:
        raise SystemExit(f"dependency {package_key[0]} {package_key[1]} is present from both source archives and Homebrew")
    formulas.setdefault(("source", *package_key), []).append(library)

known_urls = {
    "icu4c": "https://raw.githubusercontent.com/unicode-org/icu/main/LICENSE",
    "icu4c@78": "https://raw.githubusercontent.com/unicode-org/icu/main/LICENSE",
    "openssl@3": "https://raw.githubusercontent.com/openssl/openssl/master/LICENSE.txt",
    "lz4": "https://raw.githubusercontent.com/lz4/lz4/dev/lib/LICENSE",
    "zstd": "https://raw.githubusercontent.com/facebook/zstd/dev/LICENSE",
    "libxml2": "https://raw.githubusercontent.com/GNOME/libxml2/master/Copyright",
    "libxslt": "https://raw.githubusercontent.com/GNOME/libxslt/master/Copyright",
    "libgcrypt": "https://raw.githubusercontent.com/gpg/libgcrypt/master/COPYING.LIB",
    "libgpg-error": "https://raw.githubusercontent.com/gpg/libgpg-error/master/COPYING.LIB",
}
inventory = []
for (origin_kind, name, version), libraries in sorted(formulas.items()):
    if origin_kind == "source":
        source_component = source_components[(name, version)]
        target = licenses / f"{name.replace('@', '-')}-{version}.txt"
        shutil.copyfile(source_component["_license_path"], target)
        origin = source_component["license_source"]
        inventory.append({"package": name, "version": version, "libraries": libraries,
                          "license_file": target.name, "license_source": origin})
        continue

    source_paths = [pathlib.Path(sources[library]) for library in libraries]
    prefix = None
    for source_path in source_paths:
        parts = source_path.parts
        if "Cellar" in parts:
            index = parts.index("Cellar")
            candidate = pathlib.Path(*parts[:index + 3])
            if candidate.exists():
                prefix = candidate
                break
    if prefix is None:
        for cellar in (pathlib.Path("/opt/homebrew/Cellar"), pathlib.Path("/usr/local/Cellar")):
            candidate = cellar / name / version
            if candidate.exists():
                prefix = candidate
                break
    if prefix is None:
        raise SystemExit(f"cannot locate Homebrew package {name} {version}")
    candidates = sorted(
        p for p in prefix.rglob("*")
        if p.is_file() and p.name.lower() in {"license", "license.txt", "copying", "copyright"}
        and len(p.relative_to(prefix).parts) <= 5
    )
    target = licenses / f"{name.replace('@', '-')}-{version}.txt"
    if name == "e2fsprogs":
        if not all(library.startswith("libuuid") for library in libraries):
            raise SystemExit(f"e2fsprogs libraries need separate license review: {libraries}")
        origin = f"https://raw.githubusercontent.com/tytso/e2fsprogs/v{version}/lib/uuid/COPYING"
        urllib.request.urlretrieve(origin, target)
    elif candidates:
        shutil.copyfile(candidates[0], target)
        origin = str(candidates[0])
    elif name in known_urls:
        urllib.request.urlretrieve(known_urls[name], target)
        origin = known_urls[name]
    else:
        raise SystemExit(f"missing license text for bundled package {name} {version}")
    inventory.append({"package": name, "version": version, "libraries": libraries, "license_file": target.name, "license_source": origin})

(licenses / "inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
print(f"Collected {len(inventory)} dependency license texts")
