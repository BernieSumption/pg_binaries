#!/usr/bin/env python3
"""Check a retrieved Linux PostgreSQL core against its producing run and recipe inputs."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

import source_archive


ROOT = Path(__file__).resolve().parents[1]
CORE_INPUTS = (
    "scripts/linux/build.sh",
    "scripts/linux/resolve-core.sh",
    "scripts/linux/Dockerfile",
    "scripts/linux/build-in-container.sh",
    "scripts/linux/bundle-glibc-in-container.sh",
    "scripts/linux/launcher.c",
    "tools/coverage.py",
    "tools/create_linux_symbols.py",
    "tools/discover_builtins.py",
    "tools/plan_work.py",
    "tools/source_archive.py",
    "tools/license_pointer.py",
)
SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
CORE_CONFIGURE = "icu,lz4,zstd,openssl,libxml,libxslt,zlib,uuid-e2fs,no-readline,no-rpath"
CORE_RUNTIME = "bundled-glibc-static-musl-launcher"
VECTOR_VERSION = re.compile(r"pgvector-[0-9]+(?:\.[0-9]+)+")


def _valid_core_build_configuration(value, version):
    """Accept the current core-only and legacy combined Linux build contracts."""
    if not isinstance(value, str):
        return False
    fields = value.split(";")
    if fields[:1] != [f"postgresql-{version}"]:
        return False
    if len(fields) == 7:
        if not VECTOR_VERSION.fullmatch(fields[1]):
            return False
        fields.pop(1)
    expected = ["builder=ubuntu-22.04", f"configure={CORE_CONFIGURE}",
                "cflags=-O2,-g"]
    if fields[1:4] != expected:
        return False
    tail = fields[4:]
    if tail == [f"runtime={CORE_RUNTIME}"]:
        return True
    return tail == ["pgvector-optflags=empty", f"runtime={CORE_RUNTIME}"] and len(fields) == 6


def relevant_inputs_match(revision, root=ROOT):
    """Return false when a tracked core input changed after revision."""
    root = Path(root)
    if not SHA.fullmatch(str(revision)):
        raise ValueError("candidate source revision must be a full Git object ID")
    present = subprocess.run(["git", "cat-file", "-e", f"{revision}^{{commit}}"],
                             cwd=root, check=False, capture_output=True)
    if present.returncode:
        fetched = subprocess.run(["git", "fetch", "--no-tags", "--depth=1", "origin", revision],
                                 cwd=root, check=False, capture_output=True)
        if fetched.returncode:
            raise ValueError("candidate source revision is unavailable for core input comparison")
    for name in CORE_INPUTS:
        exists = subprocess.run(["git", "cat-file", "-e", f"{revision}:{name}"],
                                cwd=root, check=False, capture_output=True)
        if exists.returncode or not (root / name).is_file():
            raise ValueError(f"required core build input is unavailable: {name}")
    changed = subprocess.run(["git", "diff", "--name-only", revision, "--", *CORE_INPUTS],
                             cwd=root, check=False, capture_output=True, text=True)
    if changed.returncode:
        raise ValueError("Git could not compare candidate and current core build inputs")
    return not changed.stdout.strip()


def validate_candidate(manifest_path, archive_path, version, base_image_digest,
                       builder_packages_sha256, root=ROOT, architecture="x86_64",
                       artifact_name_template=None):
    """Require a discovered core archive to match target, producer and current recipe inputs."""
    root, archive_path = Path(root), Path(archive_path)
    try:
        discovery = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read candidate discovery manifest: {exc}") from exc
    rows = discovery.get("archives") if isinstance(discovery, dict) else None
    if (not isinstance(discovery, dict) or discovery.get("schema_version") != 1
            or not isinstance(rows, list) or len(rows) != 1):
        raise ValueError("discovery must identify exactly one checked core archive")
    row = rows[0]
    source = row.get("source") if isinstance(row, dict) else None
    if architecture not in {"x86_64", "arm64"}:
        raise ValueError(f"unsupported Linux architecture: {architecture}")
    if (not isinstance(row, dict) or row.get("component") != "postgresql" or row.get("version") != version
            or row.get("platform") != f"linux-{architecture}"
            or row.get("postgresql_version") != version
            or Path(str(row.get("path", ""))).name != archive_path.name):
        raise ValueError("discovered archive target does not match selected PostgreSQL core")
    run_id = str(source.get("run_id", "")) if isinstance(source, dict) else ""
    artifact_name = source.get("artifact_name") if isinstance(source, dict) else None
    expected_artifacts = {
        f"pgvector-linux-selected-{version}-{run_id}",
    }
    if artifact_name_template is not None:
        expected_artifacts = {artifact_name_template.replace("{run_id}", run_id)}
    if (not isinstance(source, dict) or source.get("provider") != "github-actions"
            or not re.fullmatch(r"[1-9][0-9]*", run_id)
            or not isinstance(source.get("run_attempt"), int)
            or isinstance(source.get("run_attempt"), bool) or source["run_attempt"] < 1
            or artifact_name not in expected_artifacts
            or not SHA.fullmatch(str(source.get("head_sha", "")))):
        raise ValueError("candidate lacks a checked matching Linux run and artifact identity")
    if not archive_path.is_file() or row.get("sha256") != _sha256(archive_path):
        raise ValueError("candidate archive bytes differ from discovery identity")
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            member = archive.extractfile("postgresql/manifest.json")
            if member is None:
                raise ValueError("candidate archive has no PostgreSQL manifest")
            metadata = json.load(member)
    except (OSError, tarfile.TarError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read candidate PostgreSQL manifest: {exc}") from exc
    build_revision = metadata.get("source_revision")
    if (metadata.get("component") != "postgresql" or metadata.get("version") != version
            or metadata.get("platform") != "linux" or metadata.get("architecture") != architecture
            or not SHA.fullmatch(str(build_revision))
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(metadata.get("builder_image_id", "")))):
        raise ValueError("core manifest lacks a valid target or build revision")
    if not _valid_core_build_configuration(metadata.get("build_configuration"), version):
        raise ValueError("core manifest has an unsupported build configuration")
    builder_inputs = metadata.get("builder_inputs")
    if (not isinstance(builder_inputs, dict)
            or builder_inputs.get("base_image") != "ubuntu:22.04"
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(builder_inputs.get("base_image_digest", "")))
            or not re.fullmatch(r"[0-9a-f]{64}", str(builder_inputs.get("packages_sha256", "")))):
        raise ValueError("core manifest lacks checked builder input identity")
    if (base_image_digest is None or builder_packages_sha256 is None
            or builder_inputs["base_image_digest"] != base_image_digest
            or builder_inputs["packages_sha256"] != builder_packages_sha256):
        raise ValueError("core candidate builder inputs differ from the current Linux builder")
    expected_source = source_archive.source_archive("postgresql", version, "tar.bz2", root)
    if metadata.get("source_archive") != expected_source:
        raise ValueError("core manifest source archive identity differs from selected release")
    if not relevant_inputs_match(build_revision, root):
        raise ValueError("PostgreSQL core build inputs changed after candidate source revision")
    return {"run_id": source["run_id"], "run_attempt": source["run_attempt"],
            "source_revision": build_revision, "artifact_revision": source["head_sha"],
            "sha256": row["sha256"]}


def _sha256(path):
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--base-image-digest", required=True)
    parser.add_argument("--builder-packages-sha256", required=True)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), default="x86_64")
    parser.add_argument("--artifact-name-template")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = validate_candidate(args.manifest, args.archive, args.postgresql_version,
                                    args.base_image_digest, args.builder_packages_sha256, args.root,
                                    args.architecture, args.artifact_name_template)
    except (OSError, ValueError, TypeError, KeyError, source_archive.SourceArchiveError) as exc:
        print(f"Rejected core candidate: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
