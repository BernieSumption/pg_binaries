"""Create checked Linux pgvector build identities for selected targets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_input_identity
import source_archive

VERSION = "0.8.7"
RECIPE_FILES = (
    "scripts/pgvector/linux-build.sh",
    "scripts/pgvector/builder-packages.sh",
    "scripts/pgvector/linux-build-in-container.sh",
    "scripts/pgvector/linux-build.Dockerfile",
    "scripts/pgvector/archive_input.py",
    "scripts/pgvector/build_inputs.py",
    "tools/source_archive.py",
    "tools/build_input_identity.py",
    "tools/selected_build_inputs.py",
)


def selected_identity(builder_packages_sha256: str, core_sha256: str,
                      postgresql_major: int, architecture: str,
                      pgvector_version: str = VERSION) -> dict:
    if architecture not in {"x86_64", "arm64"}:
        raise ValueError("Linux pgvector architecture must be x86_64 or arm64")
    if isinstance(postgresql_major, bool) or postgresql_major not in {15, 16, 17, 18}:
        raise ValueError("Linux pgvector path supports PostgreSQL majors 15 through 18")
    for label, value in (("builder packages", builder_packages_sha256), ("core", core_sha256)):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError(f"{label} SHA-256 must be 64 lowercase hex digits")
    support = json.loads((ROOT / "support.json").read_text(encoding="utf-8"))
    selected = support["extensions"]["pgvector"]["versions"].get(pgvector_version)
    if ("linux" not in support.get("os_support", {})
            or architecture not in support.get("platform_architectures", {}).get("linux", [])
            or not isinstance(selected, dict)
            or postgresql_major < selected.get("postgresql_minimum_major", 0)
            or postgresql_major > selected.get("postgresql_maximum_major", 99)):
        raise ValueError("pgvector target is not selected for the supported Linux matrix")
    dockerfile = (ROOT / "scripts/pgvector/linux-build.Dockerfile").read_text(encoding="utf-8")
    matches = re.findall(r"(?im)^\s*FROM\s+ubuntu:22\.04@sha256:([0-9a-f]{64})\s*$", dockerfile)
    if len(matches) != 1:
        raise ValueError("builder Dockerfile must have one pinned Ubuntu 22.04 base image")
    source = source_archive.source_archive("pgvector", pgvector_version, "tar.gz", ROOT)
    docker_arch = "amd64" if architecture == "x86_64" else "arm64"
    return build_input_identity.create_identity(
        repo_root=ROOT,
        component="pgvector",
        target={"project": "pgvector", "version": pgvector_version,
                "platform": f"linux-{architecture}", "postgresql_major": postgresql_major},
        upstream_sources={"pgvector": source},
        dependencies={
            "postgresql": {"major": postgresql_major, "sha256": core_sha256},
            "builder_packages": {"sha256": builder_packages_sha256},
            "builder_base": {"image": "ubuntu:22.04", "sha256": matches[0],
                             "platform": f"linux/{docker_arch}"},
        },
        build_configuration={"builder_image": "ubuntu:22.04", "architecture": architecture,
                             "optflags": ""},
        recipe_files=RECIPE_FILES,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--builder-packages-sha256", required=True)
    parser.add_argument("--core-sha256", required=True)
    parser.add_argument("--postgresql-major", type=int, required=True)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    parser.add_argument("--pgvector-version", default=VERSION)
    args = parser.parse_args()
    try:
        result = selected_identity(args.builder_packages_sha256, args.core_sha256,
                                   args.postgresql_major, args.architecture,
                                   args.pgvector_version)
    except (OSError, ValueError, KeyError, source_archive.SourceArchiveError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
