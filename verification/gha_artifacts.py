#!/usr/bin/env python3
"""Select build artefacts from an explicit ordered list of GitHub Actions runs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from verification.records import RecordError, selected_inputs


ROOT = Path(__file__).resolve().parents[1]
SUPPORT = json.loads((ROOT / "support.json").read_text(encoding="utf-8"))


class SelectionError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_name(target: str, component: str) -> str:
    return f"spike2-{target}-{component}"


def run_artifacts(run_id: int) -> set[str]:
    result = subprocess.run(
        ["gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/artifacts?per_page=100",
         "--paginate", "--slurp"], cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise SelectionError(f"cannot list artefacts for run {run_id}: {result.stderr.strip()}")
    try:
        pages = json.loads(result.stdout)
        return {item["name"] for page in pages for item in page["artifacts"]
                if not item.get("expired", False)}
    except (ValueError, KeyError, TypeError) as error:
        raise SelectionError(f"invalid artefact listing for run {run_id}: {error}") from error


def choose_runs(run_ids: list[int], target: str, components: list[str]) -> dict[str, int]:
    if not run_ids or any(run_id <= 0 for run_id in run_ids):
        raise SelectionError("supply positive workflow run IDs")
    selected: dict[str, int] = {}
    for run_id in run_ids:
        names = run_artifacts(run_id)
        for component in components:
            if artifact_name(target, component) in names:
                selected[component] = run_id
    missing = sorted(set(components) - set(selected))
    if missing:
        raise SelectionError(f"the supplied runs contain no build artefact for: {', '.join(missing)}")
    return selected


def download(run_id: int, name: str, directory: Path) -> None:
    directory.mkdir(parents=True)
    result = subprocess.run(
        ["gh", "run", "download", str(run_id), "--name", name, "--dir", str(directory)],
        cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise SelectionError(f"cannot download {name} from run {run_id}: {result.stderr.strip()}")


def archive_name(target: str, component: str) -> str:
    version = SUPPORT["postgresql"]["version"]
    if component == "postgresql":
        return f"postgresql-{version}-{target}.tar.gz"
    return f"{component}-postgresql-{version}-{target}.tar.gz"


def inspect_downloads(selected: dict[str, int], target: str, output: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = {"target": target, "runs": [], "components": {}}
    for component, run_id in selected.items():
        directory = output / "downloads" / component
        archive = directory / archive_name(target, component)
        record_path = directory / "record.json"
        if not archive.is_file() or not record_path.is_file():
            raise SelectionError(f"{component} artefact lacks its archive or record.json")
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise SelectionError(f"cannot read {component} record: {error}") from error
        digest = sha256(archive)
        if (record.get("component") != component or record.get("target") != target
                or record.get("archive", {}).get("filename") != archive.name
                or record.get("archive", {}).get("sha256") != digest):
            raise SelectionError(f"{component} build record does not match its archive")
        if (record.get("schema_version") != 1
                or not isinstance(record.get("git_revision"), str)
                or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", record["git_revision"])):
            raise SelectionError(f"{component} build record lacks a valid schema version or Git revision")
        try:
            sources, build_inputs = selected_inputs(SUPPORT, target, component)
        except RecordError as error:
            raise SelectionError(str(error)) from error
        if record.get("sources") != sources or record.get("build_inputs") != build_inputs:
            raise SelectionError(f"{component} build record uses different selected sources or build inputs")
        if component == "postgresql":
            development = directory / f"postgresql-development-{SUPPORT['postgresql']['version']}-{target}.tar.gz"
            if not development.is_file():
                raise SelectionError("PostgreSQL artefact lacks its development archive")
            if (record.get("development_archive", {}).get("filename") != development.name
                    or record.get("development_archive", {}).get("sha256") != sha256(development)):
                raise SelectionError("PostgreSQL development archive does not match its build record")
        manifest["components"][component] = {
            "origin_run": run_id,
            "archive": str(archive.resolve()),
            "sha256": digest,
            "build_record": str(record_path.resolve()),
        }
        if component == "postgresql":
            manifest["components"][component]["development_archive"] = str(development.resolve())
            manifest["components"][component]["development_sha256"] = sha256(development)
    postgres = manifest["components"].get("postgresql")
    if postgres:
        for component in selected:
            if component == "postgresql":
                continue
            record_path = Path(manifest["components"][component]["build_record"])
            record = json.loads(record_path.read_text(encoding="utf-8"))
            if record.get("postgresql_archive", {}).get("sha256") != postgres["sha256"]:
                raise SelectionError(f"{component} was built against a different PostgreSQL archive")
    return manifest


def select(run_ids: list[int], target: str, components: list[str], output: Path) -> dict[str, Any]:
    if "postgresql" not in components:
        raise SelectionError("selection requires the PostgreSQL artefact")
    selected = choose_runs(run_ids, target, components)
    if output.exists():
        raise SelectionError(f"output directory already exists: {output}")
    output.mkdir(parents=True)
    for component, run_id in selected.items():
        download(run_id, artifact_name(target, component), output / "downloads" / component)
    manifest = inspect_downloads(selected, target, output)
    manifest["runs"] = run_ids
    (output / "selection.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--target", choices=SUPPORT["targets"], default="macos-arm64")
    parser.add_argument("--run", action="append", required=True, type=int, dest="runs",
                        help="workflow run ID, in selection order; repeat for replacements")
    parser.add_argument("--component", action="append", choices=["postgresql", *SUPPORT["packages"]],
                        help="select only these components; default is the complete distribution")
    parser.add_argument("--verify", action="store_true", help="run the complete release check after selection")
    args = parser.parse_args(argv)
    if args.component and len(args.component) != len(set(args.component)):
        parser.error("duplicate --component")
    components = (["postgresql", *(name for name in args.component if name != "postgresql")]
                  if args.component else ["postgresql", *SUPPORT["packages"]])
    if args.verify and set(components) != {"postgresql", *SUPPORT["packages"]}:
        parser.error("verification requires every selected component")
    try:
        manifest = select(args.runs, args.target, components, args.output)
    except (SelectionError, OSError) as error:
        parser.error(str(error))
    print(args.output / "selection.json")
    if not args.verify:
        return 0
    command = [sys.executable, str(ROOT / "build.py"), "--target", args.target, "release-check",
               manifest["components"]["postgresql"]["archive"], str(args.output / "verification")]
    for component in SUPPORT["packages"]:
        command.extend(["--package-archive", f"{component}={manifest['components'][component]['archive']}"])
    for component, item in manifest["components"].items():
        command.extend(["--build-record", f"{component}={item['build_record']}"])
        command.extend(["--origin-run", f"{component}={item['origin_run']}"])
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
