"""Select and identify the checked Linux pgvector 0.8.7 build inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import build_input_identity
import source_archive as source_archive_tool


ROOT = Path(__file__).resolve().parents[1]
PROJECT = "pgvector"
VERSION = "0.8.7"
PLATFORM = "linux-x86_64"
BUILDER_PACKAGES_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PINNED_BASE = re.compile(r"(?im)^\s*FROM\s+ubuntu:22\.04@sha256:([0-9a-f]{64})\s*$")
RECIPE_FILES = (
    "scripts/pgvector/linux-build.sh",
    "scripts/pgvector/builder-packages.sh",
    "scripts/pgvector/linux-build-in-container.sh",
    "scripts/pgvector/linux-build.Dockerfile",
    "scripts/pgvector/archive_input.py",
    "tools/source_archive.py",
    "tools/build_input_identity.py",
    "tools/selected_build_inputs.py",
)


def selected_identity(builder_packages_sha256: str, postgresql_major: int = 18,
                      root: str | Path = ROOT) -> dict:
    """Return the current identity for the supported Linux pgvector target."""
    root = Path(root)
    try:
        support = json.loads((root / "support.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read support.json: {exc}") from exc
    if not isinstance(support, dict) or support.get("schema_version") != 1:
        raise ValueError("support.json has an unsupported schema")
    architectures = support.get("platform_architectures", {}).get("linux", [])
    if "linux" not in support.get("os_support", {}) or "x86_64" not in architectures:
        raise ValueError("Linux x86_64 is not supported")
    if isinstance(postgresql_major, bool) or not isinstance(postgresql_major, int):
        raise ValueError("PostgreSQL major must be an integer")
    if (not isinstance(builder_packages_sha256, str)
            or not BUILDER_PACKAGES_SHA256.fullmatch(builder_packages_sha256)):
        raise ValueError("builder packages SHA-256 must be 64 lowercase hex digits")
    if postgresql_major != 18:
        raise ValueError("the current Linux pgvector recipe supports PostgreSQL major 18 only")
    minimum = support.get("postgresql", {}).get("minimum_major")
    version = (support.get("extensions", {}).get(PROJECT, {}).get("versions", {})
               .get(VERSION))
    if not isinstance(minimum, int) or postgresql_major < minimum:
        raise ValueError(f"PostgreSQL {postgresql_major} is below the supported minimum")
    if not isinstance(version, dict):
        raise ValueError(f"{PROJECT} {VERSION} is not supported")
    if postgresql_major < version.get("postgresql_minimum_major", 0):
        raise ValueError(f"{PROJECT} {VERSION} does not support PostgreSQL {postgresql_major}")
    dockerfile = root / "scripts/pgvector/linux-build.Dockerfile"
    try:
        dockerfile_text = dockerfile.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read pinned builder Dockerfile: {exc}") from exc
    base_matches = PINNED_BASE.findall(dockerfile_text)
    if len(base_matches) != 1:
        raise ValueError("builder Dockerfile must have exactly one pinned ubuntu:22.04 base digest")
    base_sha256 = base_matches[0]
    source = source_archive_tool.source_archive(PROJECT, VERSION, "tar.gz", root)
    return build_input_identity.create_identity(
        repo_root=root,
        component=PROJECT,
        target={"project": PROJECT, "version": VERSION, "platform": PLATFORM,
                "postgresql_major": postgresql_major},
        upstream_sources={PROJECT: source},
        dependencies={"postgresql": {"major": postgresql_major},
                      "builder_packages": {"sha256": builder_packages_sha256},
                      "builder_base": {"image": "ubuntu:22.04", "sha256": base_sha256,
                                       "platform": "linux/amd64"}},
        build_configuration={"builder_image": "ubuntu:22.04", "architecture": "x86_64",
                             "optflags": ""},
        recipe_files=RECIPE_FILES,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--builder-packages-sha256", required=True,
                        help="bare lowercase SHA-256 digest of the builder package manifest")
    parser.add_argument("--postgresql-major", type=int, default=18)
    args = parser.parse_args()
    try:
        identity = selected_identity(args.builder_packages_sha256, args.postgresql_major)
    except (ValueError, source_archive_tool.SourceArchiveError) as exc:
        parser.error(str(exc))
    print(json.dumps(identity, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
