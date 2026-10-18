"""Retrieve a checksum-verified archive from a recent successful Actions run."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import zipfile

MAX_RUNS = 10
MAX_ARTIFACTS = 100
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_SIDECAR_BYTES = 4096


class DiscoveryError(ValueError):
    pass


class ApiError(DiscoveryError):
    pass


def _gh(args):
    try:
        result = subprocess.run(["gh", "api", *args], check=False, capture_output=True)
    except OSError as exc:
        raise ApiError(f"cannot run gh api: {exc}") from exc
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise ApiError(f"gh api failed: {detail or result.returncode}")
    try:
        return json.loads(result.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError(f"GitHub API returned invalid JSON: {exc}") from exc


def _expiry(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    if result.tzinfo is None:
        return None
    return result.astimezone(timezone.utc)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_matches(run, repository, workflow, branch, current_run_id):
    repo = run.get("repository")
    head_repo = run.get("head_repository")
    return (isinstance(repo, dict) and str(repo.get("full_name", "")).casefold() == repository.casefold()
            and isinstance(head_repo, dict) and str(head_repo.get("full_name", "")).casefold() == repository.casefold()
            and str(run.get("path", "")).rsplit("/", 1)[-1] == workflow
            and isinstance(run.get("head_sha"), str)
            and re.fullmatch(r"[0-9a-f]{40}", run["head_sha"]) is not None
            and run.get("head_branch") == branch
            and run.get("event") in {"push", "workflow_dispatch"}
            and run.get("status") == "completed" and run.get("conclusion") == "success"
            and str(run.get("id")) != str(current_run_id))


def _candidate_artifacts(repository, workflow, branch, current_run_id, artifact_name_template,
                         fixed_name, reasons):
    if fixed_name:
        payload = _gh([f"repos/{repository}/actions/artifacts?name={artifact_name_template}&per_page={MAX_ARTIFACTS}"])
        artifacts = payload.get("artifacts", []) if isinstance(payload, dict) else []
        artifacts = sorted((a for a in artifacts if isinstance(a, dict)),
                           key=lambda a: a.get("created_at", ""), reverse=True)[:MAX_ARTIFACTS]
        for artifact in artifacts:
            source = artifact.get("workflow_run")
            run_id = str(source.get("id", "")) if isinstance(source, dict) else ""
            if not re.fullmatch(r"[1-9][0-9]*", run_id):
                reasons.append(f"artifact {artifact.get('id', '?')}: missing source run ID")
                continue
            run = _gh([f"repos/{repository}/actions/runs/{run_id}"])
            if not isinstance(run, dict) or not _run_matches(run, repository, workflow, branch, current_run_id):
                reasons.append(f"artifact {artifact.get('id', '?')}: rejected source run identity or status")
                continue
            if source.get("head_sha") != run["head_sha"] or artifact.get("name") != artifact_name_template:
                reasons.append(f"artifact {artifact.get('id', '?')}: source identity or name mismatch")
                continue
            yield run, [artifact]
        return

    payload = _gh([f"repos/{repository}/actions/workflows/{workflow}/runs?branch={branch}&status=success&per_page={MAX_RUNS}"])
    runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
    runs = sorted((r for r in runs if isinstance(r, dict)),
                  key=lambda r: r.get("run_number", 0), reverse=True)[:MAX_RUNS]
    for run in runs:
        if not _run_matches(run, repository, workflow, branch, current_run_id):
            reasons.append(f"run {run.get('id', '?')}: rejected run identity or status")
            continue
        run_id = str(run.get("id", ""))
        artifacts_payload = _gh([f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page={MAX_ARTIFACTS}"])
        artifact_rows = artifacts_payload.get("artifacts", []) if isinstance(artifacts_payload, dict) else []
        expected_name = artifact_name_template.replace("{run_id}", run_id)
        found = [a for a in artifact_rows[:MAX_ARTIFACTS] if isinstance(a, dict) and a.get("name") == expected_name]
        if not found:
            reasons.append(f"run {run_id}: matching artifact {expected_name!r} is absent")
            continue
        yield run, found


def discover(*, repository, workflow, branch, current_run_id, artifact_name_template,
             archive_basename, project, version, platform, postgresql_version,
             output_directory, manifest_path):
    """Write a candidate manifest and retrieve the first usable matching artifact."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", workflow) or "/" in archive_basename or archive_basename in ("", ".", ".."):
        raise DiscoveryError("workflow and archive basename must be simple filenames")
    fixed_name = (isinstance(artifact_name_template, str)
                  and re.fullmatch(r"[A-Za-z0-9_.-]+", artifact_name_template) is not None
                  and artifact_name_template not in (".", ".."))
    templated_name = (isinstance(artifact_name_template, str)
                      and re.fullmatch(r"(?:[^{}]|\{run_id\})+", artifact_name_template) is not None
                      and "{run_id}" in artifact_name_template)
    if not (fixed_name or templated_name):
        raise DiscoveryError("artifact name must be a safe filename or contain a literal {run_id} placeholder")
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(manifest_path)
    reasons = []
    archives = []
    for run, found in _candidate_artifacts(repository, workflow, branch, current_run_id,
                                           artifact_name_template, fixed_name, reasons):
        run_id = str(run.get("id", ""))
        expected_name = artifact_name_template.replace("{run_id}", run_id)
        for artifact in found:
            expiry = _expiry(artifact.get("expires_at"))
            digest_claim = artifact.get("digest")
            if artifact.get("expired") is True or expiry is None or expiry <= datetime.now(timezone.utc):
                reasons.append(f"run {run_id} artifact {artifact.get('id')}: expired or invalid expiry metadata")
                continue
            if not isinstance(digest_claim, str) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest_claim):
                reasons.append(f"run {run_id} artifact {artifact.get('id')}: missing SHA-256 ZIP digest")
                continue
            reported_size = artifact.get("size_in_bytes")
            if isinstance(reported_size, int) and reported_size > MAX_ARCHIVE_BYTES:
                reasons.append(f"run {run_id} artifact {artifact.get('id')}: ZIP exceeds size limit")
                continue
            artifact_id = str(artifact.get("id", ""))
            if not re.fullmatch(r"[1-9][0-9]*", artifact_id):
                reasons.append(f"run {run_id}: artifact has invalid ID")
                continue
            try:
                archive_path, sidecar_path = _download_and_extract(
                    repository, artifact_id, digest_claim, archive_basename, output_directory)
                archive_digest = _sha256(archive_path)
                sidecar = sidecar_path.read_text(encoding="ascii").strip()
                match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?" + re.escape(archive_basename), sidecar)
                if not match or match.group(1).lower() != archive_digest:
                    raise DiscoveryError("archive sidecar checksum is missing or does not match")
                archives.append({
                    "component": "postgresql" if project.lower() == "postgresql" else "extension",
                    "project": project, "version": version, "platform": platform,
                    "postgresql_version": postgresql_version, "path": str(archive_path),
                    "sha256": archive_digest,
                    "source": {"provider": "github-actions", "run_id": run_id,
                               "head_sha": run["head_sha"], "artifact_name": expected_name,
                               "expires_at": artifact["expires_at"]},
                })
                return _write_manifest(manifest_path, archives)
            except ApiError:
                raise
            except (DiscoveryError, OSError, UnicodeError, zipfile.BadZipFile, zipfile.LargeZipFile, ValueError) as exc:
                reasons.append(f"run {run_id} artifact {artifact_id}: {exc}")
    _write_manifest(manifest_path, [])
    return reasons


def _download_and_extract(repository, artifact_id, digest_claim, basename, output_directory):
    with tempfile.TemporaryDirectory(dir=output_directory) as temporary:
        zip_path = Path(temporary) / "artifact.zip"
        try:
            with zip_path.open("wb") as sink:
                result = subprocess.run(
                    ["gh", "api", f"repos/{repository}/actions/artifacts/{artifact_id}/zip"],
                    check=False, stdout=sink, stderr=subprocess.PIPE)
        except OSError as exc:
            raise ApiError(f"cannot run gh api: {exc}") from exc
        if result.returncode:
            detail = result.stderr.decode("utf-8", "replace").strip()
            if "HTTP 404" in detail:
                raise DiscoveryError("artifact disappeared before download")
            raise ApiError(f"gh api failed: {detail or result.returncode}")
        digest = hashlib.sha256()
        size = 0
        with zip_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                if size > MAX_ARCHIVE_BYTES:
                    raise ValueError("artifact ZIP exceeds size limit")
                digest.update(chunk)
        if digest.hexdigest() != digest_claim.split(":", 1)[1].lower():
            raise ValueError("artifact ZIP digest differs from GitHub metadata")
        return _extract(zip_path, basename, output_directory)


def _extract(zip_path, basename, output_directory):
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if len(members) > 1000:
            raise DiscoveryError("artifact ZIP contains too many entries")
        candidates = {basename: [], basename + ".sha256": []}
        for item in members:
            name = item.filename
            member_path = PurePosixPath(name)
            if (member_path.is_absolute() or ".." in member_path.parts
                    or "\\" in name or (member_path.parts and ":" in member_path.parts[0])):
                raise DiscoveryError("artifact ZIP contains an unsafe path")
            if member_path.name in candidates:
                parent = member_path.parent
                if len(parent.parts) > 1:
                    continue
                if item.is_dir():
                    raise DiscoveryError("artifact ZIP has a non-file candidate entry")
                candidates[member_path.name].append((parent.as_posix(), item))
        archive_entries, sidecar_entries = candidates[basename], candidates[basename + ".sha256"]
        if len(archive_entries) > 1 or len(sidecar_entries) > 1:
            raise DiscoveryError("artifact ZIP has ambiguous duplicate candidate entries")
        if not archive_entries or not sidecar_entries:
            raise DiscoveryError("artifact ZIP lacks the exact archive and adjacent .sha256 files")
        archive_dir, archive_info = archive_entries[0]
        sidecar_dir, sidecar_info = sidecar_entries[0]
        if archive_dir != sidecar_dir:
            raise DiscoveryError("artifact ZIP archive and checksum sidecar are in different directories")
        if archive_info.file_size > MAX_ARCHIVE_BYTES or sidecar_info.file_size > MAX_SIDECAR_BYTES:
            raise DiscoveryError("archive or checksum sidecar exceeds size limit")
        archive_path = output_directory / basename
        sidecar_path = output_directory / (basename + ".sha256")
        with archive.open(archive_info) as source, archive_path.open("wb") as target:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                target.write(chunk)
        with archive.open(sidecar_info) as source, sidecar_path.open("wb") as target:
            target.write(source.read(MAX_SIDECAR_BYTES + 1))
        return archive_path, sidecar_path


def _write_manifest(path, archives):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "archives": archives}, indent=2) + "\n", encoding="utf-8")
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repository", "workflow", "branch", "current-run-id", "artifact-name-template",
                 "archive-basename", "project", "version", "platform", "postgresql-version",
                 "output-directory", "manifest-path"):
        parser.add_argument("--" + name, required=True)
    args = vars(parser.parse_args(argv))
    try:
        reasons = discover(**args)
    except DiscoveryError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for reason in reasons:
        print(reason, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
