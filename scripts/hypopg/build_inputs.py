"""Create the selected Linux HypoPG build input identity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_input_identity

VERSION = "1.4.3"
SOURCE = {
    "url": "https://github.com/HypoPG/hypopg/archive/refs/tags/1.4.3.tar.gz",
    "sha256": "498a961d88cf37057fd9e98027d06fe805c8959d51895c3d9b94c9eb4e14f706",
}
RECIPE_FILES = (
    "scripts/hypopg/build.sh",
    "scripts/hypopg/build-in-container.sh",
    "scripts/hypopg/Dockerfile",
    "scripts/hypopg/probe.sql",
    "scripts/hypopg/build_inputs.py",
    "tools/build_input_identity.py",
)


def selected_identity(core_sha256: str, builder_packages_sha256: str,
                      postgresql_version: str, architecture: str,
                      root: str | Path = ROOT) -> dict:
    if architecture not in {"x86_64", "arm64"}:
        raise ValueError("Linux HypoPG architecture must be x86_64 or arm64")
    if not isinstance(postgresql_version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+", postgresql_version):
        raise ValueError("PostgreSQL version must be an exact major.minor release")
    major = int(postgresql_version.split(".", 1)[0])
    for label, value in (("PostgreSQL core", core_sha256), ("builder packages", builder_packages_sha256)):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError(f"{label} SHA-256 must be 64 lowercase hex digits")
    root = Path(root)
    support = json.loads((root / "support.json").read_text(encoding="utf-8"))
    releases = json.loads((root / "support/postgresql-releases.json").read_text(encoding="utf-8"))
    selected = support["extensions"]["HypoPG"]["versions"].get(VERSION)
    pg_release = next((release for release in releases.get("releases", [])
                       if isinstance(release, dict) and release.get("version") == postgresql_version), None)
    supported_majors = releases.get("support_status", {}).get("supported_majors", [])
    pg_support = support.get("postgresql", {})
    pg_source = (pg_release.get("source_archives", {}).get("tar.gz")
                 if isinstance(pg_release, dict) else None)
    if ("linux" not in support.get("os_support", {})
            or architecture not in support.get("platform_architectures", {}).get("linux", [])
            or not isinstance(selected, dict)
            or not isinstance(pg_release, dict)
            or major not in supported_majors
            or major < pg_support.get("minimum_major", 0)
            or major < selected.get("postgresql_minimum_major", 0)
            or major > selected.get("postgresql_maximum_major", 99)):
        raise ValueError("HypoPG target is not selected for the supported Linux matrix")
    if (not isinstance(pg_source, dict) or not isinstance(pg_source.get("url"), str)
            or not pg_source["url"].startswith("https://")
            or not isinstance(pg_source.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", pg_source["sha256"])):
        raise ValueError(f"PostgreSQL {postgresql_version} has no valid source archive identity")
    dockerfile = (root / "scripts/hypopg/Dockerfile").read_text(encoding="utf-8")
    matches = re.findall(r"(?im)^\s*FROM\s+ubuntu:22\.04@sha256:([0-9a-f]{64})\s*$", dockerfile)
    if len(matches) != 1:
        raise ValueError("builder Dockerfile must have one pinned Ubuntu 22.04 base image")
    docker_arch = "amd64" if architecture == "x86_64" else "arm64"
    return build_input_identity.create_identity(
        repo_root=root,
        component="hypopg",
        target={"project": "hypopg", "version": VERSION,
                "platform": f"linux-{architecture}", "postgresql_version": postgresql_version},
        upstream_sources={"hypopg": SOURCE, "postgresql": pg_source},
        dependencies={
            "postgresql": {"version": postgresql_version, "sha256": core_sha256},
            "builder_packages": {"sha256": builder_packages_sha256},
            "builder_base": {"image": "ubuntu:22.04", "sha256": matches[0],
                             "platform": f"linux/{docker_arch}"},
        },
        build_configuration={"builder_image": "ubuntu:22.04", "architecture": architecture},
        recipe_files=RECIPE_FILES,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-sha256", required=True)
    parser.add_argument("--builder-packages-sha256", required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    args = parser.parse_args()
    try:
        result = selected_identity(args.core_sha256, args.builder_packages_sha256,
                                   args.postgresql_version, args.architecture)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
