#!/usr/bin/env python3
"""Resolve a successful Windows pilot core archive for reuse by a fallback build."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import actions_candidate_discovery as discovery
import postgresql_git_source
import source_archive
import windows_core_target_config


ROOT = Path(__file__).resolve().parents[1]
SHARED_CORE_INPUTS = (
    "scripts/windows", "tools/source_archive.py",
    "tools/postgresql_git_source.py", "tools/windows_core_target_config.py",
    "support/postgresql-releases.json", "support/windows-postgresql-source-identities.json",
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


def resolve(*, base_pin, output_directory, repository, branch, current_run_id, root=ROOT,
            selected_core=False):
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    base_pin = Path(base_pin)
    pin = json.loads(base_pin.read_text(encoding="utf-8"))
    version = pin.get("postgresql_version") if isinstance(pin, dict) else None
    if not isinstance(version, str):
        raise ValueError("base Windows core pin has no PostgreSQL version")
    archive_name = f"postgresql-{version}-windows-x86_64.tar.gz"
    manifest_path = output_directory / "discovery.json"
    reasons = []
    candidate_options = ([
        ("selected", SELECTED_WORKFLOW, f"windows-core-selected-{version}-build-{{run_id}}", True),
        ("pilot", "windows-pilot.yml", f"windows-postgresql-{version}-pilot", False),
    ] if selected_core else [("pilot", "windows-pilot.yml", f"windows-postgresql-{version}-pilot", False)])
    checked = None
    for kind, workflow, artifact_template, selected in candidate_options:
        candidate_reasons = discovery.discover(
            repository=repository, workflow=Path(workflow).name, branch=branch,
            current_run_id=current_run_id, artifact_name_template=artifact_template,
            archive_basename=archive_name, project="PostgreSQL", version=version,
            platform="windows-x86_64", postgresql_version=version,
            output_directory=output_directory, manifest_path=manifest_path,
        )
        reasons.extend(candidate_reasons or [])
        discovered = json.loads(manifest_path.read_text(encoding="utf-8"))
        archives = discovered.get("archives", [])
        if not archives:
            continue
        row = archives[0]
        provenance = row["source"]
        archive = Path(row["path"])
        try:
            expected_artifact = artifact_template.replace("{run_id}", str(provenance["run_id"]))
            if provenance.get("artifact_name") != expected_artifact:
                raise ValueError("producer artifact name does not match candidate workflow and run")
            target_path = output_directory / "candidate-target.json"
            target = windows_core_target_config.create_target(
                base_pin, archive, str(provenance["run_id"]), target_path,
                str(provenance["run_attempt"]), provenance["artifact_name"],
            )
            if provenance.get("head_sha") != target["source_revision"]:
                raise ValueError("producer head SHA differs from core manifest source revision")
            packaged = windows_core_target_config._manifest(archive)
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
            checked = {"status": "checked", "candidate_kind": kind,
                      "candidate_workflow": workflow, "target": str(target_path), "run_id": target["run_id"],
                      "run_attempt": provenance["run_attempt"], "source_revision": target["source_revision"],
                      "archive": str(archive), "sha256": target["sha256"]}
            break
        except (OSError, ValueError, KeyError, TypeError) as exc:
            (output_directory / "candidate-target.json").unlink(missing_ok=True)
            reasons.append(f"{kind} candidate is stale: {exc}")
    if checked:
        result = checked
    elif reasons:
        stale_reason = next((reason for reason in reasons if "candidate is stale:" in reason), None)
        result = {"status": "stale" if stale_reason else "missing",
                  "reason": stale_reason or reasons[0]}
    else:
        result = {"status": "missing", "reason": "no matching successful candidate"}
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
    parser.add_argument("--base-pin", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--branch", default=os.environ.get("GITHUB_REF_NAME"))
    parser.add_argument("--current-run-id", default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--selected-core", action="store_true",
                        help="prefer a checked selected core-only Windows build, then try the pilot")
    args = parser.parse_args(argv)
    if not all((args.repository, args.branch, args.current_run_id)):
        parser.error("repository, branch and current run ID are required (or set their GitHub environment variables)")
    try:
        result = resolve(base_pin=args.base_pin, output_directory=args.output_directory,
                         repository=args.repository, branch=args.branch,
                         current_run_id=args.current_run_id, selected_core=args.selected_core)
    except (discovery.DiscoveryError, RuntimeError, OSError, ValueError, TypeError) as exc:
        print(f"Windows core candidate: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
