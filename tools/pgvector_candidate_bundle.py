"""Retrieve the exact pgvector Linux core and extension candidate bundle."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

import actions_candidate_bundle as bundle
import actions_candidate_discovery as discovery


DIRECT_WORKFLOW = "pgvector-linux-selected-publication.yml"
DISPATCHER_WORKFLOW = "selected-extension-publication.yml"
MAX_RUNS = 100
MAX_RUN_PAGES = 10
MAX_ARTIFACTS = 100


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
    expected = {
        DIRECT_WORKFLOW,
        DISPATCHER_WORKFLOW,
    }
    encoded_branch = quote(branch, safe="")
    for page in range(1, MAX_RUN_PAGES + 1):
        payload = discovery._gh([
            f"repos/{repository}/actions/runs?branch={encoded_branch}&status=success&sort=created&direction=desc&per_page={MAX_RUNS}&page={page}"
        ])
        runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
        if not isinstance(runs, list) or not runs:
            return
        eligible = []
        for run in runs[:MAX_RUNS]:
            if not isinstance(run, dict):
                continue
            workflow = str(run.get("path", "")).rsplit("/", 1)[-1]
            if (workflow in expected and re.fullmatch(r"[1-9][0-9]*", str(run.get("id", "")))
                    and discovery._run_matches(
                    run, repository, workflow, branch, current_run_id)):
                eligible.append((workflow, run))
        eligible.sort(key=lambda item: int(item[1]["id"]), reverse=True)
        for workflow, run in eligible:
            run_id = str(run["id"])
            artifacts_payload = discovery._gh([
                f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page={MAX_ARTIFACTS}"
            ])
            artifact_rows = artifacts_payload.get("artifacts", []) if isinstance(artifacts_payload, dict) else []
            if not isinstance(artifact_rows, list):
                continue
            expected_artifact = f"pgvector-linux-selected-{pg_version}-{run_id}"
            found = [artifact for artifact in artifact_rows[:MAX_ARTIFACTS]
                     if isinstance(artifact, dict) and artifact.get("name") == expected_artifact]
            if len(found) > 1:
                raise CandidateBundleError(f"run {run_id} has duplicate exact candidate artifacts")
            if not found:
                continue
            artifact = found[0]
            source = artifact.get("workflow_run")
            if isinstance(source, dict) and (
                    str(source.get("id")) != run_id or source.get("head_sha") != run["head_sha"]):
                continue
            yield workflow, run, artifact, expected_artifact


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
            files = bundle.download_and_extract_bundle(
                repository, artifact_id, digest, basenames, output_directory,
                archive_paths=[core_archive, pgvector_archive])
        except (bundle.BundleError, OSError, ValueError) as exc:
            failures.append(f"run {run_id} artifact {artifact_id}: {exc}")
            continue
        selected = (workflow, run, artifact_name, artifact_id, expiry_text, digest, files)
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
