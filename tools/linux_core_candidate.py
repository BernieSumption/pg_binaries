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
    ".github/workflows/linux-publication.yml",
    "scripts/linux/build.sh",
    "scripts/linux/Dockerfile",
    "scripts/linux/build-in-container.sh",
    "scripts/linux/bundle-glibc-in-container.sh",
    "scripts/linux/launcher.c",
    "support.json",
    "support/postgresql-releases.json",
    "support/licences/icu-70.1-LICENSE.txt",
    "support/licences/libxml2-2.9.13-dict-notice.txt",
    "tools/coverage.py",
    "tools/create_linux_symbols.py",
    "tools/discover_builtins.py",
    "tools/plan_work.py",
    "tools/source_archive.py",
    "tools/write_linux_license_inventory.py",
)
SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def relevant_inputs_match(revision, root=ROOT):
    """Return false when any tracked core build input changed after revision."""
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
    changed = subprocess.run(["git", "diff", "--name-only", revision, "--", *CORE_INPUTS],
                             cwd=root, check=False, capture_output=True, text=True)
    if changed.returncode:
        raise ValueError("Git could not compare candidate and current core build inputs")
    return not changed.stdout.strip()


def validate_candidate(manifest_path, archive_path, version, builder_image_id, root=ROOT):
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
    if (not isinstance(row, dict) or row.get("component") != "postgresql" or row.get("version") != version
            or row.get("platform") != "linux-x86_64"
            or row.get("postgresql_version") != version
            or Path(str(row.get("path", ""))).name != archive_path.name):
        raise ValueError("discovered archive target does not match selected PostgreSQL core")
    run_id = str(source.get("run_id", "")) if isinstance(source, dict) else ""
    artifact_name = source.get("artifact_name") if isinstance(source, dict) else None
    publication_artifact = artifact_name == "linux-publication-x86_64-evidence"
    selected_artifact = artifact_name == f"pgvector-linux-selected-{version}-{run_id}"
    if (not isinstance(source, dict) or source.get("provider") != "github-actions"
            or not re.fullmatch(r"[1-9][0-9]*", run_id)
            or not isinstance(source.get("run_attempt"), int)
            or isinstance(source.get("run_attempt"), bool) or source["run_attempt"] < 1
            or not (publication_artifact or selected_artifact)
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
    if (metadata.get("component") != "postgresql" or metadata.get("version") != version
            or metadata.get("platform") != "linux" or metadata.get("architecture") != "x86_64"
            or metadata.get("source_revision") != source["head_sha"]
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(metadata.get("builder_image_id", "")))):
        raise ValueError("core manifest target or source revision differs from producer run")
    if metadata["builder_image_id"] != builder_image_id:
        raise ValueError("core candidate builder image differs from the current Linux builder image")
    expected_source = source_archive.source_archive("postgresql", version, "tar.bz2", root)
    if metadata.get("source_archive") != expected_source:
        raise ValueError("core manifest source archive identity differs from selected release")
    if not relevant_inputs_match(source["head_sha"], root):
        raise ValueError("PostgreSQL core build inputs changed after candidate source revision")
    return {"run_id": source["run_id"], "run_attempt": source["run_attempt"],
            "source_revision": source["head_sha"], "sha256": row["sha256"]}


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
    parser.add_argument("--builder-image-id", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = validate_candidate(args.manifest, args.archive, args.postgresql_version,
                                   args.builder_image_id, args.root)
    except (OSError, ValueError, TypeError, KeyError, source_archive.SourceArchiveError) as exc:
        print(f"Rejected core candidate: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
