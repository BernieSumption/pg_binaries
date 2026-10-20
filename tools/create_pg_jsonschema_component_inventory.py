#!/usr/bin/env python3
"""Create the resolved redistribution inventory for a pg_jsonschema payload."""

import argparse
import json
from pathlib import Path, PurePosixPath


REVIEWED_LICENSES = {
    "(MIT OR Apache-2.0) AND Unicode-3.0", "Apache-2.0", "Apache-2.0 OR BSL-1.0",
    "Apache-2.0 OR MIT", "Apache-2.0/MIT", "BSD-2-Clause OR Apache-2.0 OR MIT",
    "MIT", "MIT OR Apache-2.0", "MIT-0", "MIT/Apache-2.0", "Unicode-3.0",
    "Unlicense OR MIT", "Zlib",
}
REVIEW_BASIS = (
    "pg_jsonschema 0.3.4 is distributed under Apache-2.0. The target-filtered normal Cargo dependency closure "
    "declares permissive MIT, MIT-0, Apache-2.0, BSD-2-Clause, BSL-1.0, Unicode-3.0, Unlicense and Zlib terms, including "
    "dual-license alternatives. This archive retains the upstream project licence and every detected or "
    "source-verified notice for shipped crates; the seahash MIT declaration is included as exact-source evidence."
)
MODULES = {
    "linux": {"pg_jsonschema.so"},
    "macos": {"pg_jsonschema.so", "pg_jsonschema.dylib"},
    "windows": {"pg_jsonschema.dll"},
}
CARGO_INVENTORY = Path("LICENSES/cargo/cargo-license-inventory.json")
OUTPUT = Path("LICENSES/pg_jsonschema-inventory.json")


def generate(package_root, version, platform, module_filename):
    package_root = Path(package_root)
    if version != "0.3.4":
        raise ValueError(f"pg_jsonschema redistribution review does not cover {version}")
    if platform not in MODULES or module_filename not in MODULES[platform]:
        raise ValueError(f"module filename is not supported for {platform}: {module_filename}")
    project_license = package_root / "LICENSES/pg_jsonschema/LICENSE"
    if not project_license.is_file() or not project_license.stat().st_size:
        raise ValueError("missing non-empty pg_jsonschema project licence")
    inventory_path = package_root / CARGO_INVENTORY
    cargo = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
    packages = cargo.get("packages") if isinstance(cargo, dict) else None
    if not isinstance(packages, list) or not packages:
        raise ValueError("Cargo inventory has no packages")

    additional = set()
    shipped = 0
    for crate in packages:
        if not isinstance(crate, dict):
            raise ValueError("Cargo inventory package entry must be an object")
        roles = crate.get("dependency_roles", [])
        if not isinstance(roles, list):
            raise ValueError("Cargo dependency_roles must be a list")
        if "shipped" not in roles:
            continue
        shipped += 1
        name, crate_version = crate.get("name"), crate.get("version")
        if not isinstance(name, str) or not name or not isinstance(crate_version, str) or not crate_version:
            raise ValueError("shipped Cargo package requires name and version")
        license_expression = crate.get("license")
        root_declaration = (name == "pg_jsonschema" and crate_version == version
                            and license_expression is None)
        if license_expression not in REVIEWED_LICENSES and not root_declaration:
            raise ValueError(f"shipped crate licence requires review: {name} {crate_version} {license_expression}")
        notices = crate.get("packaged_license_notice_files")
        if not isinstance(notices, list) or not notices:
            raise ValueError(f"shipped crate lacks packaged notices: {name} {crate_version}")
        prefix = f"cargo/{name}-{crate_version}"
        for notice in notices:
            path = notice.get("path") if isinstance(notice, dict) else None
            if not isinstance(path, str) or not path:
                raise ValueError(f"shipped crate has an invalid notice path: {name} {crate_version}")
            relative = PurePosixPath(path)
            if (relative.is_absolute() or "\\" in path
                    or any(part in ("", ".", "..") for part in relative.parts)):
                raise ValueError(f"unsafe shipped Cargo notice path: {path}")
            normalized = path if path.startswith(prefix + "/") else f"{prefix}/{path}"
            notice_file = package_root / "LICENSES" / normalized
            if not notice_file.is_file() or not notice_file.stat().st_size:
                raise ValueError(f"missing non-empty shipped Cargo notice: {normalized}")
            additional.add(normalized)
    if shipped == 0 or not additional:
        raise ValueError("Cargo inventory has no packaged notices for shipped dependencies")

    component = {
        "component": "pg_jsonschema", "version": version,
        "payload_paths": [f"lib/{module_filename}", "share/extension"],
        "license_file": "pg_jsonschema/LICENSE",
        "additional_license_files": sorted(additional),
        "redistribution_review": {
            "status": "resolved", "basis": REVIEW_BASIS, "source_obligation": "none",
        },
    }
    inventory = {"schema_version": 1, "components": [component]}
    output_path = package_root / OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path)
    parser.add_argument("version")
    parser.add_argument("platform", choices=sorted(MODULES))
    parser.add_argument("module_filename")
    args = parser.parse_args()
    try:
        generate(args.package_root, args.version, args.platform, args.module_filename)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
