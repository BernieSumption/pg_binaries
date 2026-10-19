"""Bounded enumeration and validation for GitHub Actions candidates."""

from datetime import datetime, timezone
import re
from urllib.parse import quote

import actions_candidate_discovery as discovery

MAX_RUNS = 10
MAX_RUN_PAGES = 1
MAX_ARTIFACTS = 100
MAX_ARTIFACT_PAGES = 5
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024


class RetrievalError(ValueError):
    pass


def enumerate_successful_runs(repository, branch, current_run_id, workflow_filenames,
                              *, max_runs=MAX_RUNS, max_pages=MAX_RUN_PAGES):
    """Yield validated runs for the allowed workflow basenames, newest run ID first."""
    _identity(repository, branch, current_run_id)
    allowed = frozenset(workflow_filenames)
    if not allowed or any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name)
                          for name in allowed):
        raise RetrievalError("workflow filenames must be simple filenames")
    if not _positive_int(max_runs) or not _positive_int(max_pages):
        raise RetrievalError("run pagination limits must be positive integers")
    encoded_branch = quote(branch, safe="")
    candidates = {}
    for workflow in sorted(allowed):
        for page in range(1, max_pages + 1):
            payload = discovery._gh([
                f"repos/{repository}/actions/workflows/{workflow}/runs?"
                f"branch={encoded_branch}&status=success&per_page={max_runs}&page={page}"
            ])
            rows = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list) or not rows:
                break
            for run in rows[:max_runs]:
                if not isinstance(run, dict) or not _valid_run_id(run.get("id")):
                    continue
                if discovery._run_matches(run, repository, workflow, branch, current_run_id):
                    candidates[str(run["id"])] = (workflow, run)
            if len(rows) < max_runs:
                break
    yield from sorted(candidates.values(), key=lambda pair: int(pair[1]["id"]), reverse=True)


def exact_run_artifacts(repository, run, artifact_name_template,
                        *, max_artifacts=MAX_ARTIFACTS,
                        max_pages=MAX_ARTIFACT_PAGES):
    """Return exact-name artifacts attached to a run, reading bounded API pages."""
    run_id = str(run.get("id", "")) if isinstance(run, dict) else ""
    if not _valid_run_id(run_id):
        raise RetrievalError("run ID is invalid")
    if (not isinstance(artifact_name_template, str)
            or not re.fullmatch(r"(?:[^{}]|\{run_id\})+", artifact_name_template)
            or "{run_id}" not in artifact_name_template):
        raise RetrievalError("artifact name template must contain literal {run_id}")
    if not _positive_int(max_artifacts) or not _positive_int(max_pages):
        raise RetrievalError("artifact pagination limits must be positive integers")
    expected = artifact_name_template.replace("{run_id}", run_id)
    found = []
    for page in range(1, max_pages + 1):
        payload = discovery._gh([
            f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page={max_artifacts}&page={page}"
        ])
        rows = payload.get("artifacts", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            break
        found.extend(row for row in rows[:max_artifacts]
                     if isinstance(row, dict) and row.get("name") == expected)
        if len(rows) < max_artifacts:
            break
    if len(found) > 1:
        raise RetrievalError(f"run {run_id} has duplicate exact candidate artifacts")
    if found and not artifact_belongs_to_run(found[0], run, require_claim=True):
        return []
    return found


def artifact_belongs_to_run(artifact, run, *, require_claim=True):
    """Check the artifact's workflow_run identity against the selected run."""
    claim = artifact.get("workflow_run") if isinstance(artifact, dict) else None
    if claim is None:
        return not require_claim
    if not isinstance(claim, dict):
        return False
    return (str(claim.get("id", "")) == str(run.get("id", ""))
            and claim.get("head_sha") == run.get("head_sha")
            and ("run_attempt" not in claim or claim.get("run_attempt") == run.get("run_attempt")))


def validate_artifact_metadata(artifact, run, *, max_bytes=MAX_ARTIFACT_BYTES,
                               require_run_claim=True, require_size=False):
    """Validate expiry, digest, size and run association before downloading."""
    if not isinstance(artifact, dict) or not isinstance(run, dict):
        raise RetrievalError("artifact and source run must be objects")
    if not artifact_belongs_to_run(artifact, run, require_claim=require_run_claim):
        raise RetrievalError("artifact is not associated with the selected run")
    if artifact.get("expired") is True:
        raise RetrievalError("artifact is expired")
    expiry = discovery._expiry(artifact.get("expires_at"))
    if expiry is None or expiry <= datetime.now(timezone.utc):
        raise RetrievalError("artifact expiry is missing, invalid or elapsed")
    digest = artifact.get("digest")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise RetrievalError("artifact lacks a valid SHA-256 ZIP digest")
    size = artifact.get("size_in_bytes")
    if size is None and require_size:
        raise RetrievalError("artifact size is missing")
    if size is not None:
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise RetrievalError("artifact size is invalid")
        if size > max_bytes:
            raise RetrievalError("artifact ZIP exceeds size limit")
    return expiry, digest, size


def _identity(repository, branch, current_run_id):
    if (not isinstance(repository, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or any(part in {".", ".."} for part in repository.split("/"))):
        raise RetrievalError("repository must be owner/name")
    if not isinstance(branch, str) or not branch or any(char in branch for char in "\r\n\0"):
        raise RetrievalError("branch is invalid")
    if not _valid_run_id(current_run_id):
        raise RetrievalError("current run ID is invalid")


def _valid_run_id(value):
    return re.fullmatch(r"[1-9][0-9]*", str(value)) is not None


def _positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
