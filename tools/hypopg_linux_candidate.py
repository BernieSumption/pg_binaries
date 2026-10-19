"""Retrieve one exact selected HypoPG Linux Actions artifact as a checked manifest."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
import zipfile

import actions_candidate_bundle as bundle
import actions_candidate_discovery as discovery
import actions_candidate_retrieval as retrieval


PRODUCER_WORKFLOWS = (
    "linux-changed-profiles.yml",
    "selected-extension-publication.yml",
    "hypopg-linux-selected-publication.yml",
)
ARTIFACT_TEMPLATE = "hypopg-linux-selected-{postgresql_version}-{architecture}-{run_id}"
EXTENSION_VERSION = "1.4.3"
MAX_RUNS = 10
MAX_CANDIDATE_ATTEMPTS = 3


class CandidateRetrievalError(ValueError):
    pass


def _safe_target(repository, branch, current_run_id, postgresql_version,
                 extension_version, architecture):
    if not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise CandidateRetrievalError("repository must be owner/name")
    if not isinstance(branch, str) or not branch or any(char in branch for char in "\r\n\0"):
        raise CandidateRetrievalError("branch is invalid")
    if not re.fullmatch(r"[1-9][0-9]*", str(current_run_id)):
        raise CandidateRetrievalError("current run ID is invalid")
    if not isinstance(postgresql_version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+", postgresql_version):
        raise CandidateRetrievalError("PostgreSQL version must be exact major.minor")
    if extension_version != EXTENSION_VERSION:
        raise CandidateRetrievalError(f"Linux HypoPG recipe supports only {EXTENSION_VERSION}")
    if architecture not in {"x86_64", "arm64"}:
        raise CandidateRetrievalError("Linux architecture must be x86_64 or arm64")


def _producer_runs(repository, branch, current_run_id, postgresql_version, architecture):
    runs = retrieval.enumerate_successful_runs(
        repository, branch, current_run_id, PRODUCER_WORKFLOWS, max_runs=MAX_RUNS)
    for _, run in runs:
        run_id = str(run.get("id", ""))
        template = ARTIFACT_TEMPLATE.format(postgresql_version=postgresql_version,
                                            architecture=architecture, run_id="{run_id}")
        found = retrieval.exact_run_artifacts(
            repository, run, template)
        if found:
            yield run, found[0]


def _selected_members(zip_path, basenames, record_name):
    try:
        with zipfile.ZipFile(zip_path) as archive:
            if len(archive.infolist()) > 1000:
                raise CandidateRetrievalError("artifact ZIP contains too many entries")
            by_basename = {}
            exact_paths = set()
            for item in archive.infolist():
                if item.is_dir():
                    continue
                safe = bundle._safe_relative_path(item.filename)
                if safe in exact_paths:
                    raise CandidateRetrievalError("artifact ZIP contains duplicate paths")
                exact_paths.add(safe)
                by_basename.setdefault(PurePosixPath(safe).name, []).append(safe)
            selected = {}
            for basename in basenames:
                matches = by_basename.get(basename, [])
                if basename == record_name:
                    preferred = [path for path in matches
                                 if "-publication/records/" in "/" + path]
                    matches = preferred if len(preferred) == 1 else matches
                if len(matches) != 1:
                    raise CandidateRetrievalError(
                        f"artifact member {basename} is missing or ambiguous")
                selected[basename] = matches[0]
            return selected
    except (OSError, zipfile.BadZipFile, bundle.BundleError) as exc:
        raise CandidateRetrievalError(f"cannot inspect candidate artifact ZIP: {exc}") from exc


def retrieve(*, repository, branch, current_run_id, postgresql_version,
             extension_version=EXTENSION_VERSION,
             architecture, output_directory, manifest_path):
    """Retrieve a selected HypoPG artifact and write the semantic validator manifest."""
    _safe_target(repository, branch, current_run_id, postgresql_version,
                 extension_version, architecture)
    output_directory, manifest_path = Path(output_directory), Path(manifest_path)
    output_directory.mkdir(parents=True, exist_ok=True)
    core_name = f"postgresql-{postgresql_version}-linux-{architecture}.tar.gz"
    extension_name = (f"hypopg-{extension_version}-postgresql-{postgresql_version}-"
                      f"linux-{architecture}.tar.gz")
    record_name = (f"hypopg-{extension_version}-postgresql-{postgresql_version}-"
                   f"linux-{architecture}-current-{{run_id}}.json")
    failures = []
    attempted = 0
    for run, artifact in _producer_runs(
            repository, branch, current_run_id, postgresql_version, architecture):
        attempted += 1
        if attempted > MAX_CANDIDATE_ATTEMPTS:
            break
        run_id = str(run["id"])
        artifact_id = str(artifact.get("id", ""))
        try:
            retrieval.validate_artifact_metadata(artifact, run)
        except retrieval.RetrievalError as exc:
            failures.append(f"run {run_id}: {exc}")
            continue
        if not re.fullmatch(r"[1-9][0-9]*", artifact_id):
            failures.append(f"run {run_id}: artifact ID is invalid")
            continue
        digest_claim = artifact["digest"]
        record_basename = record_name.format(run_id=run_id)
        basenames = (core_name, core_name + ".sha256", extension_name,
                     extension_name + ".sha256", "core-resolution.json", record_basename)
        try:
            with tempfile.TemporaryDirectory(dir=output_directory) as temporary:
                zip_path = bundle._download_verified_zip(
                    repository, artifact_id, digest_claim, temporary)
                members = _selected_members(zip_path, basenames, record_basename)
                extracted = Path(temporary) / "extracted"
                mapping = bundle.extract_bundle(
                    zip_path, list(members.values()), extracted,
                    archive_paths=[members[core_name], members[extension_name]])
                staged = {}
                for basename, member in members.items():
                    source = mapping[member]
                    destination = extracted / basename
                    if source != destination:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source, destination)
                    staged[basename] = destination
                file_hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest()
                               for name, path in staged.items()}
                manifest = {
                    "schema_version": 1,
                    "target": {"postgresql_version": postgresql_version,
                               "platform": f"linux-{architecture}"},
                    "source": {"provider": "github-actions", "run_id": run_id,
                               "run_attempt": run["run_attempt"],
                               "head_sha": run["head_sha"], "repository": repository,
                               "artifact_name": artifact["name"],
                               "artifact_id": artifact_id,
                               "artifact_expires_at": artifact["expires_at"],
                               "artifact_digest": digest_claim},
                    "files": {name: str(path) for name, path in staged.items()},
                    "sha256": file_hashes,
                    "extension_record": record_basename,
                }
                # Preserve the returned paths after the temporary workspace closes.
                output_directory.mkdir(parents=True, exist_ok=True)
                destinations = [output_directory / name for name in staged]
                if manifest_path.exists() or any(path.exists() for path in destinations):
                    raise CandidateRetrievalError("candidate output destination already exists")
                for name, path in staged.items():
                    shutil.copyfile(path, output_directory / name)
                manifest["files"] = {name: str((output_directory / name).resolve())
                                     for name in staged}
                manifest_path.parent.mkdir(parents=True, exist_ok=True)
                manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                                         encoding="utf-8")
                return manifest
        except (bundle.BundleError, CandidateRetrievalError, OSError, ValueError) as exc:
            failures.append(f"run {run_id} artifact {artifact_id}: {exc}")
    detail = "; ".join(failures) if failures else "no matching successful producer artifact was found"
    raise CandidateRetrievalError(detail)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--current-run-id", required=True)
    parser.add_argument("--postgresql-version", required=True)
    parser.add_argument("--extension-version", default=EXTENSION_VERSION)
    parser.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--manifest-path", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        retrieve(**vars(args))
    except (CandidateRetrievalError, retrieval.RetrievalError, discovery.ApiError) as exc:
        print(f"hypopg-linux-candidate: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
