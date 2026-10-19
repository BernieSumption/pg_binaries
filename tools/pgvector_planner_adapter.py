"""Bind a retrieved pgvector bundle to current records and build inputs."""

import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile

import build_input_identity
import linux_core_candidate
import pgvector_candidate_records

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/pgvector"))
import build_inputs as pgvector_build_inputs


class PlannerAdapterError(ValueError):
    pass


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata(archive_path, member_name):
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            member = archive.getmember(member_name)
            if not member.isfile() or member.size >= 1024 * 1024:
                raise PlannerAdapterError(f"candidate {member_name} is not a small regular file")
            stream = archive.extractfile(member)
            metadata = json.load(stream)
            if not isinstance(metadata, dict):
                raise PlannerAdapterError(f"candidate {member_name} must be an object")
            return metadata
    except (OSError, tarfile.TarError, KeyError, json.JSONDecodeError) as exc:
        raise PlannerAdapterError(f"cannot read candidate {member_name}: {exc}") from exc


def _validate_symbols(manifest, core_name, vector_name):
    files, hashes = manifest["files"], manifest["sha256"]
    index_key = "debug-symbols/index.json"
    if index_key not in files or index_key not in hashes:
        raise PlannerAdapterError("candidate has no checked debug-symbol index")
    if _sha256(files[index_key]) != hashes[index_key]:
        raise PlannerAdapterError("debug-symbol index checksum differs from candidate manifest")
    try:
        index = json.loads(Path(files[index_key]).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlannerAdapterError(f"cannot read candidate debug-symbol index: {exc}") from exc
    if (not isinstance(index, dict) or index.get("schema_version") != 1
            or not isinstance(index.get("files"), list) or not index["files"]):
        raise PlannerAdapterError("candidate debug-symbol index is invalid")
    expected = {core_name: _sha256(files[core_name]), vector_name: _sha256(files[vector_name])}
    symbol_keys = set()
    for row in index["files"]:
        if not isinstance(row, dict) or row.get("archive_sha256") != expected.get(row.get("archive")):
            raise PlannerAdapterError("debug-symbol entry is not bound to the candidate archives")
        name = row.get("debug_file_path")
        if (not isinstance(name, str) or not name or name.startswith("/")
                or ".." in Path(name).parts or "\\" in name):
            raise PlannerAdapterError("debug-symbol index has an unsafe file path")
        key = "debug-symbols/" + name
        if key in symbol_keys or key not in files or key not in hashes:
            raise PlannerAdapterError("candidate debug-symbol file is missing or duplicated")
        digest = row.get("debug_file_sha256")
        if (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or hashes[key] != digest or _sha256(files[key]) != digest):
            raise PlannerAdapterError("candidate debug-symbol checksum differs from its index")
        symbol_keys.add(key)
    if symbol_keys != {key for key in files if key.startswith("debug-symbols/") and key != index_key}:
        raise PlannerAdapterError("candidate contains unindexed debug symbols")


def checked_candidate_inputs(manifest, root=ROOT, *, core_base_image_digest,
                             core_builder_packages_sha256,
                             pgvector_builder_packages_sha256):
    """Return planner inputs only after checking records, core provenance and identities."""
    root = Path(root)
    if isinstance(manifest, (str, Path)):
        try:
            manifest = json.loads(Path(manifest).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PlannerAdapterError(f"cannot read candidate bundle manifest: {exc}") from exc
    try:
        records = pgvector_candidate_records.validate_candidate_records(manifest, root)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        raise PlannerAdapterError(str(exc)) from exc
    target = manifest["target"]
    pg, version, platform = (target["postgresql_version"], target["pgvector_version"],
                             target["platform"])
    architecture = platform.removeprefix("linux-")
    core_name = f"postgresql-{pg}-{platform}.tar.gz"
    vector_name = f"pgvector-{version}-postgresql-{pg}-{platform}.tar.gz"
    _validate_symbols(manifest, core_name, vector_name)
    core_path = Path(manifest["files"][core_name])
    vector_path = Path(manifest["files"][vector_name])
    source = manifest["source"]

    # Reuse the full Linux core candidate validator, adapting the selected bundle's
    # already-checked record/run identity to its discovery-manifest input contract.
    discovery = {"schema_version": 1, "archives": [{
        "component": "postgresql", "version": pg, "postgresql_version": pg,
        "platform": platform, "path": str(core_path), "sha256": _sha256(core_path),
        "source": {"provider": "github-actions", "run_id": str(source["run_id"]),
                   "run_attempt": source["run_attempt"], "head_sha": source["head_sha"],
                   "artifact_name": source["artifact_name"]},
    }]}
    with tempfile.TemporaryDirectory(prefix="pgvector-planner-") as temporary:
        discovery_path = Path(temporary) / "core-discovery.json"
        discovery_path.write_text(json.dumps(discovery), encoding="utf-8")
        try:
            core_provenance = linux_core_candidate.validate_candidate(
                discovery_path, core_path, pg, core_base_image_digest,
                core_builder_packages_sha256, root=root, architecture=architecture,
                artifact_name_template=f"pgvector-linux-selected-{pg}-{{run_id}}")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise PlannerAdapterError(f"core candidate rejected: {exc}") from exc

    core_sha = _sha256(core_path)
    vector_metadata = _metadata(vector_path, "metadata.json")
    try:
        expected_vector_identity = pgvector_build_inputs.selected_identity(
            pgvector_builder_packages_sha256, core_sha, int(pg.split(".", 1)[0]),
            architecture, version)
    except (OSError, ValueError, KeyError) as exc:
        raise PlannerAdapterError(f"cannot compute current pgvector build identity: {exc}") from exc
    assessment = build_input_identity.assess_reuse(
        expected_vector_identity, vector_metadata.get("build_inputs"))
    if not assessment["reusable"]:
        raise PlannerAdapterError(f"pgvector candidate build inputs differ: {assessment['reason']}")

    run_source = {"provider": "github-actions", "run_id": str(source["run_id"]),
                  "artifact_name": source["artifact_name"],
                  "expires_at": source["artifact_expires_at"]}
    vector_sha = _sha256(vector_path)
    core_manifest = _metadata(core_path, "postgresql/manifest.json")
    record_names = {
        "core": f"postgresql-{pg}-{platform}-current-{source['run_id']}.json",
        "extension": (f"pgvector-{version}-postgresql-{pg}-{platform}-current-"
                      f"{source['run_id']}.json"),
    }
    current_records = []
    for kind, record in records.items():
        current_records.append({**record, "_profile_current": True,
                                "_record_file": record_names[kind]})
    checked_core = {
        "component": "postgresql", "version": pg, "postgresql_version": pg,
        "platform": platform, "path": str(core_path.resolve()),
        "archive_name": core_path.name, "sha256": core_sha,
        "source_claims": {**run_source, "run_attempt": source["run_attempt"],
                          "head_sha": source["head_sha"]},
        "source_revision": core_provenance["source_revision"],
        "build_inputs": core_manifest["builder_inputs"],
        "validation": "linux-core-candidate-and-current-inputs",
    }
    checked_vector = {
        "component": "pgvector", "project": "pgvector", "version": version,
        "platform": platform, "postgresql_version": pg,
        "path": str(vector_path.resolve()), "archive_name": vector_path.name,
        "sha256": vector_sha, "source_claims": run_source,
        "build_input_identity": expected_vector_identity,
        "validation": "current-pgvector-build-input-identity",
    }
    return {
        "planner_overlay": {
            "schema_version": 1,
            "candidate_archives": [checked_core, checked_vector],
            "verification_records": current_records,
        },
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--core-base-image-digest", required=True)
    parser.add_argument("--core-builder-packages-sha256", required=True)
    parser.add_argument("--pgvector-builder-packages-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = checked_candidate_inputs(
            args.manifest, args.root, core_base_image_digest=args.core_base_image_digest,
            core_builder_packages_sha256=args.core_builder_packages_sha256,
            pgvector_builder_packages_sha256=args.pgvector_builder_packages_sha256)
    except (PlannerAdapterError, ValueError, OSError, TypeError, KeyError) as exc:
        print(f"pgvector-planner-adapter: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
