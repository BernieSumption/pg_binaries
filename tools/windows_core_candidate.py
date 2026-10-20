#!/usr/bin/env python3
"""Resolve an explicitly pinned unpublished Windows core archive for reuse."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import postgresql_git_source
import source_archive
import windows_core_pin as core_pin
import windows_core_target
import windows_core_target_config


ROOT = Path(__file__).resolve().parents[1]
SHARED_CORE_INPUTS = (
    "scripts/windows", "tools/source_archive.py",
    "tools/postgresql_git_source.py", "tools/windows_core_target_config.py",
)
PILOT_WORKFLOW = ".github/workflows/windows-pilot.yml"
SELECTED_WORKFLOW = ".github/workflows/postgresql-windows-selected-publication.yml"


def _relevant_inputs_match(revision, root=ROOT, selected=False):
    present = subprocess.run(["git", "cat-file", "-e", f"{revision}^{{commit}}"],
                             cwd=root, check=False, capture_output=True)
    if present.returncode:
        fetched = subprocess.run(["git", "fetch", "--no-tags", "--depth=1", "origin", revision],
                                 cwd=root, check=False, capture_output=True)
        if fetched.returncode:
            raise RuntimeError("cannot retrieve Windows core source revision for input comparison")
    workflow = SELECTED_WORKFLOW if selected else PILOT_WORKFLOW
    inputs = SHARED_CORE_INPUTS + (workflow,)
    result = subprocess.run(["git", "diff", "--quiet", revision, "--", *inputs],
                            cwd=root, check=False, capture_output=True)
    if result.returncode == 1:
        return False
    if result.returncode:
        raise RuntimeError("git diff could not verify Windows core inputs")
    return True


def _run_json(repository, run_id):
    result = subprocess.run(["gh", "api", f"repos/{repository}/actions/runs/{run_id}"],
                            check=False, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"cannot retrieve pinned Windows core run: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub returned invalid pinned Windows core run JSON") from exc


def _download_pin(pin, output_directory, repository, branch, current_run_id):
    run = _run_json(repository, pin["run_id"])
    expected_workflow = pin["workflow"]
    head_repository = run.get("head_repository") if isinstance(run, dict) else None
    source_repository = run.get("repository") if isinstance(run, dict) else None
    attempt = run.get("run_attempt") if isinstance(run, dict) else None
    valid = (isinstance(run, dict) and isinstance(source_repository, dict)
             and isinstance(head_repository, dict)
             and str(source_repository.get("full_name", "")).casefold() == repository.casefold()
             and str(head_repository.get("full_name", "")).casefold() == repository.casefold()
             and str(run.get("id")) == str(pin["run_id"])
             and isinstance(attempt, int) and not isinstance(attempt, bool) and attempt > 0
             and run.get("head_branch") == branch
             and run.get("event") in {"push", "workflow_dispatch"}
             and run.get("status") == "completed" and run.get("conclusion") == "success"
             and str(run.get("path", "")).rsplit("/", 1)[-1] == expected_workflow
             and run.get("head_sha") and re.fullmatch(r"[0-9a-f]{40}", run["head_sha"]) is not None
             and str(pin["run_id"]) != str(current_run_id))
    if not valid:
        raise ValueError("pinned Windows core builder run does not match its artifact pin")
    download_dir = output_directory / "pinned-artifact"
    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded = subprocess.run(
        ["gh", "run", "download", str(pin["run_id"]), "--repo", repository,
         "--name", pin["artifact_name"], "--dir", str(download_dir)],
        check=False, capture_output=True, text=True)
    if downloaded.returncode:
        raise FileNotFoundError(f"pinned Windows core artifact is unavailable: {downloaded.stderr.strip()}")
    archives = list(download_dir.rglob(pin["archive_name"]))
    sidecars = list(download_dir.rglob(pin["archive_name"] + ".sha256"))
    if len(archives) != 1 or len(sidecars) != 1:
        raise ValueError("pinned Windows core artifact must contain one archive and checksum sidecar")
    archive = output_directory / pin["archive_name"]
    sidecar = Path(str(archive) + ".sha256")
    archive.write_bytes(archives[0].read_bytes())
    sidecar.write_bytes(sidecars[0].read_bytes())
    digest = windows_core_target_config._sha256(archive)
    if digest != pin["sha256"]:
        raise ValueError("pinned Windows core archive checksum differs")
    return run, str(attempt), archive


def resolve(*, base_pin=None, base_target=None, output_directory, repository, branch, current_run_id, root=ROOT,
            selected_core=False, artifact_pin_path=None):
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    if (base_pin is None) == (base_target is None):
        raise ValueError("provide exactly one of base_target or legacy base_pin")
    base_target_path = Path(base_target if base_target is not None else base_pin)
    base = windows_core_target.load_target(
        base_target_path, root=root, allow_identity_template=True)
    version = base.get("postgresql_version")
    if not isinstance(version, str):
        raise ValueError("base Windows core target has no PostgreSQL version")
    try:
        pin = core_pin.load_artifact_pin(version, artifact_pin_path)
    except core_pin.MissingArtifactPin as exc:
        result = {"status": "missing", "reason": str(exc)}
    except (OSError, ValueError, TypeError) as exc:
        result = {"status": "stale", "reason": f"Windows core artifact pin is invalid: {exc}"}
    else:
        try:
            if selected_core and pin["workflow"] != "postgresql-windows-selected-publication.yml":
                raise ValueError("selected publication requires a pin from its core-only Windows workflow")
            run, attempt, archive = _download_pin(pin, output_directory, repository, branch, current_run_id)
            target_path = output_directory / "candidate-target.json"
            target = windows_core_target_config.create_target(
                base_target_path, archive, str(pin["run_id"]), target_path,
                attempt, pin["artifact_name"], root=root)
            if run.get("head_sha") != target["source_revision"]:
                raise ValueError("producer head SHA differs from core manifest source revision")
            packaged = windows_core_target_config._manifest(archive)
            selected = pin["workflow"] == "postgresql-windows-selected-publication.yml"
            if selected and not _selected_build_configuration(packaged, version):
                raise ValueError("candidate does not identify the selected core-only Windows builder recipe")
            if not _relevant_inputs_match(target["source_revision"], root, selected=selected):
                raise ValueError("Windows core recipe or source identity changed since candidate")
            if version == "16.15":
                if packaged.get("source_checkout") != postgresql_git_source.source_checkout(version, root):
                    raise ValueError("candidate PostgreSQL Git source identity is stale")
                if "source_archive" in packaged or "source_sha256" in packaged:
                    raise ValueError("Git checkout candidate claims release archive identity")
            else:
                expected = source_archive.source_archive("postgresql", version, "tar.gz", root)
                if packaged.get("source_archive") != expected or packaged.get("source_sha256") != expected["sha256"]:
                    raise ValueError("candidate PostgreSQL source archive identity is stale")
            result = {"status": "checked", "candidate_kind": "selected" if selected else "pilot",
                      "candidate_workflow": pin["workflow"], "target": str(target_path),
                      "run_id": target["run_id"], "run_attempt": attempt,
                      "source_revision": target["source_revision"], "archive": str(archive),
                      "sha256": target["sha256"]}
        except FileNotFoundError as exc:
            result = {"status": "missing", "reason": str(exc)}
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            (output_directory / "candidate-target.json").unlink(missing_ok=True)
            result = {"status": "stale", "reason": f"pinned candidate is stale: {exc}"}
    (output_directory / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _selected_build_configuration(manifest, version):
    value = manifest.get("build_configuration") if isinstance(manifest, dict) else None
    if not isinstance(value, str) or "pgvector-" in value:
        return False
    fields = value.split(";")
    expected_prefix = [f"postgresql-{version}", "builder=windows-runner"]
    if fields[:2] != expected_prefix or "compiler=MSVC" not in fields or "runtime=vcpkg-and-msvc-dlls" not in fields:
        return False
    if version == "15.19":
        return len(fields) > 2 and fields[2] == "postgresql-builder=msvc-release"
    return "meson=debugoptimized" in fields


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    base = parser.add_mutually_exclusive_group(required=True)
    base.add_argument("--base-target", type=Path)
    base.add_argument("--base-pin", type=Path, help="legacy full identity template")
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME"))
    parser.add_argument("--current-run-id", default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--selected-core", action="store_true",
                        help="accept the selected core-only Windows builder recipe")
    parser.add_argument("--artifact-pin", type=Path,
                        help="exact unpublished core artifact pin (defaults to the versioned support pin)")
    args = parser.parse_args(argv)
    if not all((args.repository, args.branch, args.current_run_id)):
        parser.error("repository, branch and current run ID are required (or set their GitHub environment variables)")
    try:
        result = resolve(base_pin=args.base_pin, base_target=args.base_target,
                         output_directory=args.output_directory,
                         repository=args.repository, branch=args.branch,
                         current_run_id=args.current_run_id, selected_core=args.selected_core,
                         artifact_pin_path=args.artifact_pin)
    except (RuntimeError, OSError, ValueError, TypeError) as exc:
        print(f"Windows core candidate: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
