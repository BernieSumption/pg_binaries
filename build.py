#!/usr/bin/env python3
"""Run the package build operations used locally and by build jobs."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from build_support.metadata import packages


ROOT = Path(__file__).resolve().parent
SUPPORT = json.loads((ROOT / "support.json").read_text(encoding="utf-8"))
PACKAGES = packages()


def release_module(target: str) -> str:
    if target.startswith("linux-"):
        return "verification.linux.release"
    if target.startswith("windows-"):
        return "verification.windows.release"
    return "verification.macos.release"


def run_recipe(path: Path, arguments: list[str], target: str) -> None:
    if target.startswith("windows-"):
        path = path.with_suffix(".ps1")
    if not path.is_file():
        raise SystemExit(f"No {target} recipe: {path.relative_to(ROOT)}")
    environment = os.environ.copy()
    if target.startswith("macos-"):
        environment["MACOSX_DEPLOYMENT_TARGET"] = SUPPORT["targets"][target]["minimum_os_version"]
        environment["COPYFILE_DISABLE"] = "1"
    command = (["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"]
               if target.startswith("windows-") else ["bash"])
    result = subprocess.run([*command, str(path), *arguments], env=environment, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="macos-arm64", choices=SUPPORT["targets"])
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare-dependencies", help="Prepare system build dependencies for one package")
    prepare.add_argument("component", choices=["postgresql", *PACKAGES])

    postgres_build = commands.add_parser("postgresql-build", help="Compile and install PostgreSQL")
    postgres_build.add_argument("workspace", help="Empty directory for the PostgreSQL build")
    postgres_build.add_argument("--source-cache", help="Verified download cache outside the workspace")

    postgres_package = commands.add_parser("postgresql-package", help="Create PostgreSQL runtime and development archives")
    postgres_package.add_argument("workspace")
    postgres_package.add_argument("output_dir")

    extension_build = commands.add_parser("extension-build", help="Build one extension package")
    extension_build.add_argument("package", choices=PACKAGES)
    extension_build.add_argument("development_archive", help="PostgreSQL development archive or extracted installation")
    extension_build.add_argument("output_dir")
    extension_build.add_argument("--workspace", help="Build directory without whitespace; defaults to a new temporary directory")
    extension_build.add_argument("--source-cache", help="Verified download cache outside the workspace")
    extension_build.add_argument("--reuse-workspace", action="store_true",
                                 help="Retain this package's sources and build intermediates for local iteration")

    archive_check = commands.add_parser("archive-check", help="Validate archive contents and overlaps")
    archive_check.add_argument("archives", nargs="+")

    record = commands.add_parser("build-record", help="Record a produced archive and its selected inputs")
    record.add_argument("component", choices=["postgresql", *PACKAGES])
    record.add_argument("archive")
    record.add_argument("output")
    record.add_argument("--revision", required=True)
    record.add_argument("--postgresql-archive")
    record.add_argument("--development-archive")

    runtime_check = commands.add_parser("runtime-check", help="Test extracted archives in a fresh installation")
    runtime_check.add_argument("postgresql_archive")
    runtime_check.add_argument("output_parent")
    runtime_check.add_argument("--package-archive", action="append", default=[], metavar="PACKAGE=ARCHIVE")

    release_check = commands.add_parser("release-check", help="Verify selected archives in every required combination")
    release_check.add_argument("postgresql_archive")
    release_check.add_argument("output_dir")
    release_check.add_argument("--package-archive", action="append", default=[], metavar="PACKAGE=ARCHIVE")
    release_check.add_argument("--build-record", action="append", default=[], metavar="COMPONENT=PATH")
    release_check.add_argument("--origin-run", action="append", default=[], metavar="COMPONENT=RUN_ID")

    select_runs = commands.add_parser("select-runs", help="Select build artefacts from explicit workflow runs")
    select_runs.add_argument("output_dir")
    select_runs.add_argument("--run", action="append", required=True, type=int, dest="runs",
                             help="workflow run ID, in selection order")
    select_runs.add_argument("--component", action="append", choices=["postgresql", *PACKAGES])
    select_runs.add_argument("--verify", action="store_true", help="run the complete release check")

    inventory = commands.add_parser("inventory-draft", help="Draft inventory.json from complete verification reports")
    inventory.add_argument("reports", nargs="+")
    inventory.add_argument("--tag", required=True, help="intended immutable GitHub release tag")
    inventory.add_argument("--output", required=True, help="new inventory JSON path")

    publication = commands.add_parser("publication-preflight", help="Check draft inventory against local verified archive bytes")
    publication.add_argument("inventory")
    publication.add_argument("--target", action="append", required=True, dest="target_pairs",
                             metavar="TARGET=SELECTION.json,REPORT.json")

    args = parser.parse_args()
    target = args.target
    postgres_recipe = ROOT / "packages" / "postgresql" / "build.sh"
    target_parts = target.split("-", 1)

    if args.command == "prepare-dependencies":
        if target.startswith("linux-"):
            result = subprocess.run([sys.executable, str(ROOT / "platforms/linux/prepare_dependencies.py"), args.component], check=False)
            if result.returncode:
                raise SystemExit(result.returncode)
        elif target.startswith("windows-"):
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                     "-File", str(ROOT / "platforms/windows/bootstrap.ps1"), "-Package", args.component], check=False)
            if result.returncode:
                raise SystemExit(result.returncode)
        else:
            run_recipe(ROOT / "platforms/macos/prepare-dependencies.sh", [args.component], target)
    elif args.command == "postgresql-build":
        from build_support.metadata import load_package
        from build_support.sources import prepare_sources
        workspace = Path(args.workspace).resolve()
        if any(character.isspace() for character in str(workspace)):
            parser.error("PostgreSQL build workspaces must have paths without whitespace")
        cache = Path(args.source_cache).expanduser().resolve() if args.source_cache else Path.home() / ".cache/pg_binaries/sources"
        if workspace == cache or workspace in cache.parents:
            parser.error("source cache must be outside the workspace")
        workspace.mkdir(parents=True, exist_ok=True)
        if any(workspace.iterdir()):
            parser.error("PostgreSQL workspace must be empty")
        prepare_sources(load_package("postgresql")["sources"], workspace / "sources", cache)
        (workspace / "build").mkdir()
        (workspace / "payload").mkdir()
        run_recipe(postgres_recipe, [*target_parts, str(workspace)], target)
    elif args.command == "postgresql-package":
        from build_support.postgresql import package_postgresql
        print(json.dumps(package_postgresql(Path(args.workspace).resolve(), target, Path(args.output_dir).resolve())))
    elif args.command == "extension-build":
        from build_support.extensions import build_extension
        arguments = [args.package, target, args.development_archive, args.output_dir,
                     args.workspace, args.source_cache]
        if args.reuse_workspace:
            arguments.append(True)
        print(build_extension(*arguments))
    elif args.command == "archive-check":
        result = subprocess.run([sys.executable, str(ROOT / "verification" / "archive.py"), *args.archives], check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
    elif args.command == "build-record":
        command = [sys.executable, str(ROOT / "verification" / "records.py"),
                   "--target", target, "--component", args.component,
                   "--revision", args.revision, "--archive", args.archive,
                   "--output", args.output]
        if args.postgresql_archive:
            command.extend(["--postgresql-archive", args.postgresql_archive])
        if args.development_archive:
            command.extend(["--development-archive", args.development_archive])
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
    elif args.command == "runtime-check":
        command = [sys.executable, "-m", "verification.runtime", args.postgresql_archive, args.output_parent,
                   "--target", target]
        for package_archive in args.package_archive:
            command.extend(["--package-archive", package_archive])
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
    elif args.command == "release-check":
        command = [sys.executable, "-m", release_module(target), args.postgresql_archive, args.output_dir,
                   "--target", target]
        for package_archive in args.package_archive:
            command.extend(["--package-archive", package_archive])
        for build_record in args.build_record:
            command.extend(["--build-record", build_record])
        for origin_run in args.origin_run:
            command.extend(["--origin-run", origin_run])
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
    elif args.command == "select-runs":
        command = [sys.executable, "-m", "verification.gha_artifacts", args.output_dir,
                   "--target", target]
        for run_id in args.runs:
            command.extend(["--run", str(run_id)])
        for component in args.component or []:
            command.extend(["--component", component])
        if args.verify:
            command.append("--verify")
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
    elif args.command == "inventory-draft":
        command = [sys.executable, "-m", "verification.inventory", *args.reports,
                   "--tag", args.tag, "--output", args.output]
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
    elif args.command == "publication-preflight":
        command = [sys.executable, "-m", "verification.publication_preflight", args.inventory]
        for target_selection in args.target_pairs:
            command.extend(["--target", target_selection])
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
