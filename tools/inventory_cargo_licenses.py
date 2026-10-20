#!/usr/bin/env python3
"""Write a deterministic licence and notice inventory from Cargo metadata."""

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path


LICENSE_FILE = re.compile(r"^(LICENSE|LICENCE|COPYING|COPYRIGHT|NOTICE)([-.]|$)", re.IGNORECASE)


def file_inventory(root):
    files = []
    if not root.is_dir():
        return files
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        in_license_directory = len(relative.parts) > 1 and relative.parts[0].upper() in {"LICENSES", "LICENCES"}
        if path.is_file() and (LICENSE_FILE.match(path.name) or in_license_directory):
            files.append({
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    return files


def _proc_macro(package):
    return any("proc-macro" in target.get("kind", [])
               or "proc-macro" in target.get("crate_types", [])
               for target in package.get("targets", []))


def dependency_roles(metadata):
    """Classify resolved packages by whether their code is linked or host tooling."""
    resolve = metadata.get("resolve")
    if not isinstance(resolve, dict) or not resolve.get("root"):
        raise ValueError("Cargo metadata must include a resolved root package")

    packages = {package["id"]: package for package in metadata.get("packages", []) if "id" in package}
    nodes = {node["id"]: node for node in resolve.get("nodes", []) if "id" in node}
    root = resolve["root"]
    if root not in packages or root not in nodes:
        raise ValueError("Cargo metadata resolved root is missing from packages or resolve.nodes")

    roles = {package_id: set() for package_id in packages}
    roles[root].update(("root", "shipped"))
    pending = [(root, "shipped")]
    visited = set()
    while pending:
        package_id, context = pending.pop()
        state = (package_id, context)
        if state in visited:
            continue
        visited.add(state)
        node = nodes.get(package_id)
        if node is None:
            continue
        for dep in node.get("deps", []):
            target_id = dep.get("pkg")
            target = packages.get(target_id)
            if target is None:
                continue
            kinds = dep.get("dep_kinds") or [{"kind": None}]
            for dep_kind in kinds:
                kind = dep_kind.get("kind")
                if context == "shipped" and kind not in (None, "normal"):
                    roles[target_id].update(("host_tooling", f"{kind}_dependency"))
                    pending.append((target_id, "host"))
                elif context == "shipped" and _proc_macro(target):
                    roles[target_id].update(("host_tooling", "proc_macro"))
                    pending.append((target_id, "host"))
                elif context == "shipped":
                    roles[target_id].add("shipped")
                    pending.append((target_id, "shipped"))
                else:
                    roles[target_id].update(("host_tooling", f"{kind or 'normal'}_dependency"))
                    if _proc_macro(target):
                        roles[target_id].add("proc_macro")
                    pending.append((target_id, "host"))
    return roles


def inventory(source_root, metadata):
    source_root = source_root.resolve()
    roles = dependency_roles(metadata)
    packages = []
    for package in sorted(metadata.get("packages", []), key=lambda p: (p["name"], p["version"], p.get("source") or "")):
        manifest = Path(package["manifest_path"]).resolve()
        crate_root = manifest.parent
        declared = package.get("license")
        license_file = package.get("license_file")
        if license_file:
            license_path = (crate_root / license_file).resolve()
            if not license_path.is_relative_to(crate_root) or not license_path.is_file() or not license_path.stat().st_size:
                raise ValueError(f"invalid or missing license_file for {package['name']} {package['version']}: {license_file}")
        files = file_inventory(crate_root)
        if license_file and Path(license_file).as_posix() not in {item["path"] for item in files}:
            files.append({"path": Path(license_file).as_posix(),
                          "sha256": hashlib.sha256(license_path.read_bytes()).hexdigest()})
            files.sort(key=lambda item: item["path"])
        packages.append({
            "name": package["name"],
            "version": package["version"],
            "source": package.get("source"),
            "repository": package.get("repository"),
            "license": declared,
            "license_file": Path(license_file).as_posix() if license_file else None,
            "license_metadata_missing": not declared and not license_file,
            "license_notice_files": files,
            "dependency_roles": sorted(roles.get(package.get("id"), {"unreachable"})),
        })
    return {
        "schema_version": 1,
        "source_files": file_inventory(source_root),
        "packages": packages,
    }


SUPPLEMENTS = {
    "pgrx": ("0.16.1", "2e515ae3fe3d350258ce9cd492ce41a7afcbaaef", "pgrx-v0.16.1-LICENSE",
             "074f7499b019ffe4bc37b61842f709ccd8bf9800c456e6a2d14f0353c4973fe3", "https://github.com/pgcentralfoundation/pgrx"),
    "uuid-simd": ("0.8.0", "d74c030d9dc4f3cae02146d1f497ff62726ef09a", "simd-v0.8.0-LICENSE",
                  "71674605ec4c087fe9eb534e3e4f9e26eb2e4aabcd76a29fd156c6a844d44b3d", "https://github.com/Nugine/simd"),
}
SUPPLEMENTS["pgrx-pg-sys"] = SUPPLEMENTS["pgrx"]
SUPPLEMENTS["pgrx-sql-entity-graph"] = SUPPLEMENTS["pgrx"]
SUPPLEMENTS["vsimd"] = SUPPLEMENTS["uuid-simd"]

SEAHASH_IDENTITY = {
    "version": "4.1.0",
    "source": "registry+https://github.com/rust-lang/crates.io-index",
    "license": "MIT",
    "repository": "https://gitlab.redox-os.org/redox-os/seahash",
    "evidence_file": "seahash-4.1.0-license-declaration.txt",
}
SEAHASH_EVIDENCE = (
    b"Package: seahash 4.1.0\nDeclared license: MIT\n"
    b"Cargo source: registry+https://github.com/rust-lang/crates.io-index\n"
    b"Upstream repository: https://gitlab.redox-os.org/redox-os/seahash\n"
    b"Upstream source commit: https://gitlab.redox-os.org/redox-os/seahash/-/tree/94b632aeac099031c373599313d5b5f0acbbaec0\n"
    b"Evidence: https://docs.rs/crate/seahash/4.1.0/source/Cargo.toml.orig (published licence declaration)\n"
)
SEAHASH_EVIDENCE_SHA256 = hashlib.sha256(SEAHASH_EVIDENCE).hexdigest()


def _safe_relative(value):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or not path.parts:
        raise ValueError(f"unsafe licence path: {value}")
    return path


def package_notices(result, metadata, payload, supplements):
    """Copy shipped-package texts, retaining provenance and unresolved packages."""
    by_package = {(p["name"], p["version"], p.get("source")): Path(p["manifest_path"]).resolve().parent
                  for p in metadata["packages"]}
    missing = []
    for package in result["packages"]:
        if "shipped" not in package["dependency_roles"]:
            continue
        name, version = package["name"], package["version"]
        crate = by_package[(name, version, package.get("source"))]
        target = Path("cargo") / _safe_relative(f"{name}-{version}")
        notices = []
        for notice in package["license_notice_files"]:
            relative = _safe_relative(notice["path"])
            source = (crate / relative).resolve()
            if not source.is_relative_to(crate):
                raise ValueError(f"licence escapes crate: {name}/{relative}")
            notices.append((source, target / relative, notice["sha256"], {"crate_path": notice["path"]}))
        if name in SUPPLEMENTS:
            expected_version, commit, filename, digest, repository = SUPPLEMENTS[name]
            vcs = json.loads((crate / ".cargo_vcs_info.json").read_text(encoding="utf-8"))
            if (version != expected_version or vcs.get("git", {}).get("sha1") != commit
                    or package.get("source") != "registry+https://github.com/rust-lang/crates.io-index"):
                raise ValueError(f"supplement source identity mismatch: {name} {version}")
            notices.append((supplements / filename, target / "upstream-LICENSE", digest,
                            {"source_url": f"{repository}/blob/{commit}/LICENSE", "source_commit": commit}))
        if name == "seahash":
            identity = SEAHASH_IDENTITY
            if (version != identity["version"] or package.get("source") != identity["source"]
                    or package.get("license") != identity["license"]
                    or package.get("repository") != identity["repository"]):
                raise ValueError("seahash source identity mismatch")
            evidence = supplements / identity["evidence_file"]
            if evidence.read_bytes() != SEAHASH_EVIDENCE:
                raise ValueError("seahash declaration evidence changed")
            notices.append((evidence, target / identity["evidence_file"],
                            SEAHASH_EVIDENCE_SHA256,
                            {"source_url": "https://docs.rs/crate/seahash/4.1.0/source/Cargo.toml.orig",
                             "upstream_repository": identity["repository"],
                             "declared_license": identity["license"]}))
        package["packaged_license_notice_files"] = []
        for source, relative, digest, provenance in notices:
            content = source.read_bytes()
            if not content or hashlib.sha256(content).hexdigest() != digest:
                raise ValueError(f"licence content missing or changed: {source}")
            destination = payload / "LICENSES" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            package["packaged_license_notice_files"].append(
                {"path": relative.as_posix(), "sha256": digest, **provenance})
        if not notices:
            missing.append({"name": name, "version": version, "source": package.get("source")})
    result["packaging"] = {"scope": "shipped normal dependency closure including root",
                           "missing_notice_packages": missing, "redistribution_review": "pending"}
    if missing:
        raise ValueError(f"unexpected unresolved shipped-package notices: {missing}")


def check_packaged_notices(archive, inventory_name):
    """Check the final archive against the mapped notice bytes without extraction."""
    members = archive.getmembers()
    names = [member.name for member in members]
    if len(names) != len(set(names)):
        raise ValueError("duplicate archive members")
    result = json.load(archive.extractfile(inventory_name))
    if result.get("packaging", {}).get("redistribution_review") != "pending":
        raise ValueError("missing pending Cargo notice packaging record")
    if not result.get("packages"):
        raise ValueError("empty Cargo package inventory")
    for package in result["packages"]:
        if "shipped" not in package["dependency_roles"]:
            continue
        notices = package.get("packaged_license_notice_files", [])
        if not notices:
            raise ValueError(f"missing shipped-package notices: {package['name']}")
        prefix = f"cargo/{package['name']}-{package['version']}/"
        expected = {prefix + notice["path"]: notice["sha256"]
                    for notice in package["license_notice_files"]}
        if package["name"] in SUPPLEMENTS:
            expected_version, commit, filename, digest, repository = SUPPLEMENTS[package["name"]]
            if package["version"] != expected_version:
                raise ValueError("supplement version mismatch")
            expected[prefix + "upstream-LICENSE"] = digest
        if package["name"] == "seahash":
            identity = SEAHASH_IDENTITY
            if (package["version"] != identity["version"] or package.get("source") != identity["source"]
                    or package.get("license") != identity["license"]):
                raise ValueError("seahash source identity mismatch")
            if package.get("repository") != identity["repository"]:
                raise ValueError("seahash source identity mismatch")
            expected[prefix + identity["evidence_file"]] = SEAHASH_EVIDENCE_SHA256
            seahash_notice = next((notice for notice in notices
                                   if notice.get("path") == prefix + identity["evidence_file"]), None)
            if (seahash_notice is None or seahash_notice.get("source_url") != "https://docs.rs/crate/seahash/4.1.0/source/Cargo.toml.orig"
                    or seahash_notice.get("upstream_repository") != identity["repository"]
                    or seahash_notice.get("declared_license") != "MIT"):
                raise ValueError("seahash declaration evidence mapping changed")
        if {notice["path"]: notice["sha256"] for notice in notices} != expected:
            raise ValueError(f"notice mapping differs from source inventory: {package['name']}")
        for notice in notices:
            relative = _safe_relative(notice["path"])
            member = archive.getmember("pg_jsonschema/LICENSES/" + relative.as_posix())
            if not member.isfile() or not member.size:
                raise ValueError(f"missing regular notice: {member.name}")
            if hashlib.sha256(archive.extractfile(member).read()).hexdigest() != notice["sha256"]:
                raise ValueError(f"changed notice: {member.name}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-archive", type=Path)
    parser.add_argument("--archive-inventory")
    parser.add_argument("source_root", type=Path, nargs="?")
    parser.add_argument("cargo_metadata", type=Path, nargs="?", help="JSON from cargo metadata --locked --format-version 1")
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--supplements", type=Path)
    args = parser.parse_args()
    if args.check_archive:
        if not args.archive_inventory:
            parser.error("--check-archive requires --archive-inventory")
        with tarfile.open(args.check_archive, "r:gz") as archive:
            check_packaged_notices(archive, args.archive_inventory)
        return
    if not all((args.source_root, args.cargo_metadata, args.output)):
        parser.error("source_root, cargo_metadata and output are required")
    if bool(args.package_root) != bool(args.supplements):
        parser.error("--package-root and --supplements must be supplied together")
    metadata = json.loads(args.cargo_metadata.read_text(encoding="utf-8"))
    result = inventory(args.source_root, metadata)
    if args.package_root:
        package_notices(result, metadata, args.package_root, args.supplements)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
