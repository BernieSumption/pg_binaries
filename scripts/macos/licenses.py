#!/usr/bin/env python3
"""Collect licence texts for libraries embedded in a pilot archive."""

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import sys
import urllib.request


parser = argparse.ArgumentParser()
parser.add_argument("package_root")
parser.add_argument("source_manifest", nargs="?")
parser.add_argument("--component", required=True, choices=("postgresql", "pgvector"))
parser.add_argument("--version", required=True)
parser.add_argument("--source-url", required=True)
parser.add_argument("--source-sha256")
args = parser.parse_args()
root = pathlib.Path(args.package_root).resolve()
licenses = root / "LICENSES"
licenses.mkdir(exist_ok=True)
sources = json.loads((root / "bundled-dependencies.json").read_text())
formulas = {}
source_manifest = None
source_prefix = None
source_components = {}
source_libraries = {}

if args.source_manifest:
    manifest_path = pathlib.Path(args.source_manifest).resolve()
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
        if source_manifest is not None:
            raise SystemExit(f"source-built dependency bundle still includes Homebrew library {library}: {source}")
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
pending_review = {"status": "pending", "basis": "Redistribution terms and source obligations require review.",
                  "source_obligation": "unknown"}
reviewed_source = {
    ("icu4c", "78.3"): (
        "3a2e7a47604ba702f345878308e6fefeca612ee895cf4a5f222e7955fabfe0c0",
        "e55522d81edc687a341a4411e0776e54ca654e90147f354a90458aaced4116af",
        {"libicudata.78.3.dylib", "libicui18n.78.3.dylib", "libicuuc.78.3.dylib"},
        "ICU 78.3 release LICENSE contains the Unicode License v3 and third-party notices for its binary libraries and data; retaining that text permits redistribution without source delivery. https://unicode-org.github.io/icu/userguide/icu/release.html",
    ),
    ("libxslt", "1.1.45"): (
        "9acfe68419c4d06a45c550321b3212762d92f41465062ca4ea19e632ee5d216e",
        "7e48e290b6bfccc2ec1b297023a1d77f2fd87417f71fbb9f50aabef40a851819",
        {"libxslt.1.dylib"},
        "libxslt 1.1.45 Copyright contains the permission and copyright notice for its bundled library; retaining that text permits binary redistribution without source delivery. https://gitlab.gnome.org/GNOME/libxslt/-/tags/v1.1.45",
    ),
    ("libxml2", "2.15.4"): (
        "98087fd181d9070724f3fbc65c7377db03038eb92bd882374daff44940138821",
        "5d4873884a890122a4b9b20ad56ac6f7da1d796a5bfcf04a427970ac96217626",
        {"libxml2.16.dylib"},
        "libxml2 2.15.4 Copyright grants redistribution of the library with its copyright and permission notice; it excludes dict.c and list.c, whose complete separate header notices are also retained. None of these notices requires source delivery. https://github.com/GNOME/libxml2/blob/v2.15.4/Copyright",
        ["ea9e97f88bf4ef8ad1142e12d0e6da003968420aa38094f74b9b51206675438a",
         "2fdb83809864852d236c64fffa74054699e61887b736e18724d4a8ac0e9684f8"],
    ),
    ("lz4", "1.10.0"): (
        "537512904744b35e232912055ccf8ec66d768639ff3abe5788d90d792ec5f48b",
        "8b58c446121a109ccf32edc094bba3010a3d85e4ee3702950db55e4d3e87736c",
        {"liblz4.1.10.0.dylib"},
        "LZ4 1.10.0 lib/LICENSE applies BSD-2-Clause to this library-only payload; retaining its notice permits binary redistribution without source delivery. https://github.com/lz4/lz4/blob/v1.10.0/lib/LICENSE",
    ),
    ("openssl", "3.5.8"): (
        "a8f84a39918ec6415ce765d9b429d313ba97b8143169c172e734b9514464f5b2",
        "7d5450cb2d142651b8afa315b5f238efc805dad827d91ba367d8516bc9d49e7a",
        {"libcrypto.3.dylib", "libssl.3.dylib"},
        "OpenSSL 3.5.8 LICENSE.txt grants Apache-2.0 redistribution of these libraries with the included licence; the source tag has no root NOTICE file and imposes no source-delivery condition. https://github.com/openssl/openssl/blob/openssl-3.5.8/LICENSE.txt",
    ),
    ("zstd", "1.5.7"): (
        "eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3",
        "7055266497633c9025b777c78eb7235af13922117480ed5c674677adc381c9d8",
        {"libzstd.1.5.7.dylib"},
        "Zstandard 1.5.7 LICENSE permits BSD-3-Clause redistribution of this library-only payload with the included notice and no source delivery. https://github.com/facebook/zstd/blob/v1.5.7/LICENSE",
    ),
}
reviewed_primary = {
    ("postgresql", "18.6"): (
        "https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2",
        "555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f",
        "3d6af92ff8a4c2cdf69afb1cf44edea727922f5cd0cf8b5f72b11cdecac8fdfd",
        "PostgreSQL 18.6 COPYRIGHT permits binary redistribution when its copyright, permission and disclaimer paragraphs accompany copies; the complete source text is retained here. It does not require source delivery. https://github.com/postgres/postgres/blob/REL_18_6/COPYRIGHT",
    ),
    ("pgvector", "0.8.7"): (
        "https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.7.tar.gz",
        "cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85",
        "6bba9ebeb73e27477463b05e5ef1bf303bccbddb3db9bbc95905d351604d6a87",
        "pgvector 0.8.7 LICENSE permits binary redistribution when its copyright, permission and disclaimer paragraphs accompany copies; the complete source text is retained here. It does not require source delivery. https://github.com/pgvector/pgvector/blob/v0.8.7/LICENSE",
    ),
}
inventory = []

def payload_paths(libraries):
    paths = []
    for library in sorted(libraries):
        path = root / "lib" / library
        if pathlib.Path(library).name != library or not path.is_file() or not path.resolve().is_relative_to(root):
            raise SystemExit(f"missing or unsafe bundled library payload: {library}")
        paths.append(path.relative_to(root).as_posix())
    return paths


def dependency_entry(name, version, libraries, target, origin):
    return {"component": name, "package": name, "version": version, "libraries": sorted(libraries),
            "payload_paths": payload_paths(libraries), "license_file": target.name,
            "license_source": origin, "redistribution_review": dict(pending_review)}

for (origin_kind, name, version), libraries in sorted(formulas.items()):
    if origin_kind == "source":
        source_component = source_components[(name, version)]
        target = licenses / f"{name.replace('@', '-')}-{version}.txt"
        shutil.copyfile(source_component["_license_path"], target)
        origin = source_component["license_source"]
        entry = dependency_entry(name, version, libraries, target, origin)
        entry.update({key: source_component[key] for key in ("source_url", "source_sha256")})
        reviewed = reviewed_source.get((name, version))
        additional = source_component.get("additional_license_files", [])
        if not isinstance(additional, list):
            raise SystemExit(f"additional_license_files must be a list for {name}")
        for index, filename in enumerate(additional):
            if not isinstance(filename, str) or not filename:
                raise SystemExit(f"invalid additional licence path for {name}")
            source_path = (source_manifest.parent / filename).resolve()
            if not source_path.is_relative_to(source_manifest.parent) or not source_path.is_file() or not source_path.stat().st_size:
                raise SystemExit(f"missing or unsafe additional licence text for {name}: {filename}")
            notice = licenses / f"{target.stem}-notice-{index + 1}.txt"
            shutil.copyfile(source_path, notice)
            entry.setdefault("additional_license_files", []).append(notice.name)
        if reviewed is not None:
            source_digest, licence_digest, expected_libraries, basis, *notice_digests = reviewed
            actual_notices = [hashlib.sha256((licenses / filename).read_bytes()).hexdigest()
                              for filename in entry.get("additional_license_files", [])]
            expected_notices = notice_digests[0] if notice_digests else []
            if (source_component["source_sha256"] == source_digest
                    and hashlib.sha256(target.read_bytes()).hexdigest() == licence_digest
                    and set(libraries) == expected_libraries
                    and actual_notices == expected_notices):
                entry["redistribution_review"] = {
                    "status": "resolved", "basis": basis, "source_obligation": "none"}
        inventory.append(entry)
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
    if not target.stat().st_size:
        raise SystemExit(f"empty licence text for {name} {version}")
    inventory.append(dependency_entry(name, version, libraries, target, origin))

primary_license = "PostgreSQL.txt" if args.component == "postgresql" else "pgvector.txt"
if not (licenses / primary_license).is_file() or not (licenses / primary_license).stat().st_size:
    raise SystemExit(f"missing primary licence text: {primary_license}")
dependency_payloads = {path for entry in inventory for path in entry["payload_paths"]}
primary_payloads = sorted(path.relative_to(root).as_posix() for directory in ("bin", "lib", "share", "include")
                          for path in (root / directory).rglob("*")
                          if path.is_file() and path.relative_to(root).as_posix() not in dependency_payloads)
if not primary_payloads:
    raise SystemExit(f"no primary payload for {args.component}")
primary = {"component": args.component, "version": args.version, "payload_paths": primary_payloads,
           "license_file": primary_license, "source_url": args.source_url,
           "redistribution_review": dict(pending_review)}
if args.source_sha256:
    if not re.fullmatch(r"[0-9a-f]{64}", args.source_sha256):
        raise SystemExit("primary source_sha256 must be 64 lowercase hexadecimal digits")
    primary["source_sha256"] = args.source_sha256
reviewed = reviewed_primary.get((args.component, args.version))
if reviewed is not None:
    source_url, source_digest, license_digest, basis = reviewed
    if (args.source_url == source_url and args.source_sha256 == source_digest
            and hashlib.sha256((licenses / primary_license).read_bytes()).hexdigest() == license_digest):
        primary["redistribution_review"] = {
            "status": "resolved", "basis": basis, "source_obligation": "none"}
inventory.insert(0, primary)
(licenses / "inventory.json").write_text(json.dumps({"schema_version": 1, "components": inventory}, indent=2, sort_keys=True) + "\n")
print(f"Collected {len(inventory)} dependency license texts")
