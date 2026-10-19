"""Retrieve the exact pgvector Linux core and extension candidate bundle."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import zipfile

import actions_candidate_bundle as bundle
import actions_candidate_discovery as discovery
import actions_candidate_retrieval as retrieval


DIRECT_WORKFLOW = "pgvector-linux-selected-publication.yml"
DISPATCHER_WORKFLOW = "selected-extension-publication.yml"
MAX_CANDIDATE_ATTEMPTS = 3
SYMBOL_INDEX = "_temp/bundle/pilot/debug-symbols/index.json"
SYMBOL_ROOT = "_temp/bundle/pilot/debug-symbols/"


class CandidateBundleError(ValueError):
    pass


def _safe_identity(repository, branch, current_run_id, version, postgresql_version, architecture):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", str(repository)):
        raise CandidateBundleError("repository must be owner/name")
    if not isinstance(branch, str) or not branch or any(c in branch for c in "\r\n\0"):
        raise CandidateBundleError("branch is invalid")
    if not re.fullmatch(r"[1-9][0-9]*", str(current_run_id)):
        raise CandidateBundleError("current run ID is invalid")
    for value, label in ((version, "pgvector version"), (postgresql_version, "PostgreSQL minor")):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", value):
            raise CandidateBundleError(f"{label} is invalid")
    if architecture not in {"x86_64", "arm64"}:
        raise CandidateBundleError("Linux architecture must be x86_64 or arm64")


def _run_candidates(repository, branch, current_run_id, pg_version):
    runs = retrieval.enumerate_successful_runs_global(
        repository, branch, current_run_id,
        (DIRECT_WORKFLOW, DISPATCHER_WORKFLOW), max_runs=100, max_pages=10)
    for workflow, run in runs:
        run_id = str(run["id"])
        expected_artifact = f"pgvector-linux-selected-{pg_version}-{run_id}"
        try:
            found = retrieval.exact_run_artifacts(
                repository, run, "pgvector-linux-selected-" + pg_version + "-{run_id}",
                max_artifacts=100, max_pages=1, require_run_claim=False,
                require_attempt_match=False, ignore_malformed_claim=True)
        except retrieval.RetrievalError as exc:
            raise CandidateBundleError(str(exc)) from exc
        if found:
            yield workflow, run, found[0], expected_artifact


def _symbol_paths(archive, core_name, vector_name, core_member, vector_member):
    """Validate the selected artifact's symbol index and return its exact allowlist."""
    try:
        with zipfile.ZipFile(archive) as source:
            index = json.loads(source.read(SYMBOL_INDEX))
            by_name = {item.filename: item for item in source.infolist() if not item.is_dir()}
            symbol_members = {
                bundle._safe_relative_path(item.filename)
                for item in source.infolist()
                if not item.is_dir() and item.filename.startswith(SYMBOL_ROOT)
                and item.filename != SYMBOL_INDEX
            }
    except (KeyError, OSError, ValueError, zipfile.BadZipFile, UnicodeError) as exc:
        raise CandidateBundleError(f"debug-symbol index is missing or invalid: {exc}") from exc
    if not isinstance(index, dict) or index.get("schema_version") != 1 or not isinstance(index.get("files"), list):
        raise CandidateBundleError("debug-symbol index has an unsupported schema")
    try:
        with zipfile.ZipFile(archive) as source:
            archive_hashes = {
                core_name: hashlib.sha256(source.read(core_member)).hexdigest(),
                vector_name: hashlib.sha256(source.read(vector_member)).hexdigest(),
            }
    except (KeyError, OSError, zipfile.BadZipFile) as exc:
        raise CandidateBundleError("selected archives are missing from the artifact") from exc
    expected_paths = set()
    try:
        with zipfile.ZipFile(archive) as source:
            for row in index["files"]:
                if not isinstance(row, dict):
                    raise CandidateBundleError("debug-symbol index contains an invalid entry")
                archive_name = row.get("archive")
                archive_hash = row.get("archive_sha256")
                debug_path = row.get("debug_file_path")
                debug_hash = row.get("debug_file_sha256")
                if archive_name not in archive_hashes or archive_hash != archive_hashes[archive_name]:
                    raise CandidateBundleError("debug-symbol entry is not bound to the selected core or pgvector archive")
                if not isinstance(debug_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", debug_hash):
                    raise CandidateBundleError("debug-symbol entry has an invalid file checksum")
                try:
                    safe_path = bundle._safe_relative_path(debug_path)
                except bundle.BundleError as exc:
                    raise CandidateBundleError(f"debug-symbol path is unsafe: {debug_path!r}") from exc
                if safe_path in expected_paths:
                    raise CandidateBundleError("debug-symbol index contains duplicate paths")
                expected_paths.add(safe_path)
                member = SYMBOL_ROOT + safe_path
                if member not in by_name:
                    raise CandidateBundleError(f"debug-symbol file is missing: {debug_path}")
                digest = hashlib.sha256()
                with source.open(member) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest() != debug_hash.lower():
                    raise CandidateBundleError(f"debug-symbol checksum mismatch: {debug_path}")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise CandidateBundleError("debug-symbol file cannot be read") from exc
    if not expected_paths or symbol_members != {SYMBOL_ROOT + path for path in expected_paths}:
        raise CandidateBundleError("debug-symbol files are missing, extra, or unsafe")
    return [SYMBOL_ROOT + path for path in sorted(expected_paths)], index


def retrieve(*, repository, branch, current_run_id, version, postgresql_version,
             architecture, output_directory, manifest_path):
    """Retrieve one verified producer artifact and write paths plus its provenance."""
    _safe_identity(repository, branch, current_run_id, version, postgresql_version, architecture)
    candidates = _run_candidates(repository, branch, current_run_id, postgresql_version)
    pgvector_archive = f"pgvector-{version}-postgresql-{postgresql_version}-linux-{architecture}.tar.gz"
    core_archive = f"postgresql-{postgresql_version}-linux-{architecture}.tar.gz"
    output_directory = Path(output_directory)
    failures = []
    selected = None
    saw_candidate = False
    for workflow, run, artifact, artifact_name in candidates:
        if len(failures) >= MAX_CANDIDATE_ATTEMPTS:
            break
        saw_candidate = True
        expiry_text = artifact.get("expires_at")
        expiry = discovery._expiry(expiry_text)
        now = datetime.now(timezone.utc)
        digest = artifact.get("digest")
        artifact_id = str(artifact.get("id", ""))
        run_id = str(run["id"])
        verification_core = f"postgresql-{postgresql_version}-linux-{architecture}-current-{run_id}.json"
        verification_extension = (
            f"pgvector-{version}-postgresql-{postgresql_version}-linux-{architecture}-current-{run_id}.json")
        basenames = [core_archive, core_archive + ".sha256", pgvector_archive, pgvector_archive + ".sha256",
                     verification_core, verification_extension]
        artifact_paths = {
            name: (f"_temp/bundle/pilot/publication/records/{name}" if name.endswith(".json")
                   else f"_temp/bundle/pilot/{name}")
            for name in basenames
        }
        if artifact.get("expired") is True or expiry is None or expiry <= now:
            failures.append(f"run {run_id}: artifact expired or expiry metadata invalid")
            continue
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
            failures.append(f"run {run_id}: artifact lacks GitHub ZIP SHA-256 metadata")
            continue
        if not re.fullmatch(r"[1-9][0-9]*", artifact_id):
            failures.append(f"run {run_id}: artifact ID is invalid")
            continue
        if isinstance(artifact.get("size_in_bytes"), int) and artifact["size_in_bytes"] > bundle.MAX_ARCHIVE_BYTES:
            failures.append(f"run {run_id}: artifact ZIP exceeds size limit")
            continue
        try:
            output_directory.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=output_directory) as temporary:
                zip_path = bundle._download_verified_zip(repository, artifact_id, digest, temporary)
                symbol_paths, symbol_index = _symbol_paths(
                    zip_path, core_archive, pgvector_archive,
                    artifact_paths[core_archive], artifact_paths[pgvector_archive])
                requested_paths = list(artifact_paths.values()) + [SYMBOL_INDEX] + symbol_paths
                files = bundle.extract_bundle(
                    zip_path, requested_paths, output_directory,
                    archive_paths=[artifact_paths[core_archive], artifact_paths[pgvector_archive]])
                for row in symbol_index["files"]:
                    symbol_key = "debug-symbols/" + row["debug_file_path"]
                    files[symbol_key] = files.pop(SYMBOL_ROOT + row["debug_file_path"])
                files["debug-symbols/index.json"] = files.pop(SYMBOL_INDEX)
        except (bundle.BundleError, OSError, ValueError) as exc:
            failures.append(f"run {run_id} artifact {artifact_id}: {exc}")
            continue
        manifest_files = {name: files[path] for name, path in artifact_paths.items()}
        manifest_files.update({key: value for key, value in files.items()
                               if key.startswith("debug-symbols/")})
        selected = (workflow, run, artifact_name, artifact_id, expiry_text, digest, manifest_files)
        break
    if selected is None:
        if not saw_candidate:
            raise CandidateBundleError("no successful eligible run has the exact pgvector selected artifact")
        detail = "; ".join(failures)
        raise CandidateBundleError("no eligible candidate artifact could be retrieved" + (f": {detail}" if detail else ""))
    workflow, run, artifact_name, artifact_id, expiry_text, digest, files = selected
    paths = {name: str(path.resolve()) for name, path in files.items()}
    manifest = {
        "schema_version": 1,
        "eligibility": "candidate bundle retrieved; profile and build-input checks remain",
        "target": {"pgvector_version": version, "postgresql_version": postgresql_version,
                   "platform": f"linux-{architecture}"},
        "files": paths,
        "sha256": {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                   for name, path in paths.items()},
        "source": {"repository": repository, "workflow": workflow, "branch": branch,
                   "run_id": str(run["id"]), "run_attempt": run["run_attempt"], "head_sha": run["head_sha"],
                   "artifact_id": artifact_id, "artifact_name": artifact_name,
                   "artifact_expires_at": expiry_text, "artifact_zip_digest": digest},
    }
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repository", "branch", "current-run-id", "version", "postgresql-version",
                 "architecture", "output-directory", "manifest-path"):
        parser.add_argument("--" + name, required=True)
    args = vars(parser.parse_args(argv))
    try:
        retrieve(**args)
    except (CandidateBundleError, discovery.ApiError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
