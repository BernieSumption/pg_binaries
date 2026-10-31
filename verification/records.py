#!/usr/bin/env python3
"""Write build records from package inputs and the produced archive bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_support.metadata import load_selection


class RecordError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RecordError(f"cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def selected_inputs(support: dict[str, Any], target: str,
                    component: str, root: Path = ROOT) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if target not in support.get("targets", {}):
        raise RecordError(f"unsupported target: {target}")
    selection = (support.get("postgresql") if component == "postgresql"
                 else support.get("packages", {}).get(component))
    if not isinstance(selection, dict):
        raise RecordError(f"unknown component: {component}")
    package_dir = root / "packages" / component
    input_paths = [package_dir / "build.json", package_dir / "build.sh"]
    input_paths.extend(path for name in ("build-dependencies.sh", "build.ps1", "build-dependencies.ps1")
                       if (path := package_dir / name).is_file())
    input_paths.extend(path for path in (package_dir / "internal").rglob("*")
                       if path.is_file() and "__pycache__" not in path.parts
                       and path.suffix not in (".pyc", ".pyo") and path.name != ".DS_Store")
    build_inputs = {"files": {str(path.relative_to(package_dir)): sha256_file(path)
                             for path in sorted(input_paths)}}
    sources = [{"id": name, **source} for name, source in sorted(selection.get("sources", {}).items())]
    if not sources:
        raise RecordError(f"no selected downloadable sources found for {component} on {target}")
    return sources, build_inputs


def make_record(support_path: Path, target: str, component: str,
                archive_path: Path, revision: str,
                postgresql_archive: Optional[Path] = None,
                development_archive: Optional[Path] = None) -> dict[str, Any]:
    try:
        support = load_selection(support_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise RecordError(f"cannot read support file {support_path}: {exc}") from exc

    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise RecordError("Git revision must be a full lowercase commit hash")

    if component == "postgresql":
        if postgresql_archive is not None:
            raise RecordError("PostgreSQL records do not take --postgresql-archive")
    else:
        if postgresql_archive is None:
            raise RecordError("extension records require --postgresql-archive")
        if development_archive is not None:
            raise RecordError("extension records do not take --development-archive")
    sources, build_inputs = selected_inputs(support, target, component, support_path.parent)
    manifest_name = "postgresql-build.json" if component == "postgresql" else "extension-build.json"
    manifest_path = archive_path.parent / manifest_name
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RecordError(f"cannot read build output manifest {manifest_path}: {exc}") from exc
    version = manifest.get("version") if component == "postgresql" else manifest.get("postgresql_version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9][a-zA-Z0-9._-]*", version):
        raise RecordError("build output manifest has no valid PostgreSQL version")
    if manifest.get("archive") != {"filename": archive_path.name, "sha256": sha256_file(archive_path)}:
        raise RecordError("build output manifest does not match produced archive")

    record: dict[str, Any] = {
        "schema_version": 1,
        "component": component,
        "target": target,
        "git_revision": revision.strip(),
        "postgresql_version": version,
        "sources": sources,
        "build_inputs": build_inputs,
        "archive": {"filename": archive_path.name, "sha256": sha256_file(archive_path)},
    }
    if postgresql_archive is not None:
        expected_postgresql = {"filename": postgresql_archive.name, "sha256": sha256_file(postgresql_archive)}
        if manifest.get("postgresql_archive") != expected_postgresql:
            raise RecordError("PostgreSQL archive does not match the development installation used for compilation")
        record["postgresql_archive"] = {
            "filename": postgresql_archive.name,
            "sha256": sha256_file(postgresql_archive),
        }
        development_input = manifest.get("postgresql_development_archive")
        if development_input is not None:
            if (not isinstance(development_input, dict) or not isinstance(development_input.get("filename"), str)
                    or Path(development_input["filename"]).name != development_input["filename"]
                    or not isinstance(development_input.get("sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", development_input["sha256"])):
                raise RecordError("invalid development archive compilation input")
            record["postgresql_development_archive"] = development_input
    if development_archive is not None:
        if manifest.get("development_archive") != {"filename": development_archive.name,
                                                   "sha256": sha256_file(development_archive)}:
            raise RecordError("build output manifest does not match development archive")
        record["development_archive"] = {
            "filename": development_archive.name,
            "sha256": sha256_file(development_archive),
        }
    return record


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--support", type=Path, default=Path(__file__).resolve().parents[1] / "support.json")
    parser.add_argument("--target", required=True)
    parser.add_argument("--component", required=True,
                        help="postgresql or a discovered extension package")
    parser.add_argument("--revision", required=True, help="Git commit revision")
    parser.add_argument("--archive", required=True, type=Path,
                        help="produced .tar.gz archive")
    parser.add_argument("--postgresql-archive", type=Path,
                        help="PostgreSQL archive used to compile an extension")
    parser.add_argument("--development-archive", type=Path,
                        help="PostgreSQL development archive produced alongside the runtime archive")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        record = make_record(args.support, args.target, args.component,
                             args.archive, args.revision, args.postgresql_archive,
                             args.development_archive)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    except (RecordError, OSError) as exc:
        print(f"build record failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
