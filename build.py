#!/usr/bin/env python3
"""Run the package build operations used locally and by build jobs."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
SUPPORT = json.loads((ROOT / "support.json").read_text(encoding="utf-8"))


def run_recipe(path: Path, arguments: list[str], target: str) -> None:
    if not path.is_file():
        raise SystemExit(f"No {target} recipe: {path.relative_to(ROOT)}")
    environment = os.environ.copy()
    environment["MACOSX_DEPLOYMENT_TARGET"] = SUPPORT["targets"][target]["minimum_os_version"]
    environment["COPYFILE_DISABLE"] = "1"
    result = subprocess.run(["bash", str(path), *arguments], env=environment, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="macos-arm64", choices=SUPPORT["targets"])
    commands = parser.add_subparsers(dest="command", required=True)

    dependencies = commands.add_parser("postgresql-dependencies", help="Build PostgreSQL's pinned dependencies")
    dependencies.add_argument("prefix")

    postgres_build = commands.add_parser("postgresql-build", help="Compile and install PostgreSQL")
    postgres_build.add_argument("dependency_prefix")
    postgres_build.add_argument("build_dir")
    postgres_build.add_argument("install_prefix")

    postgres_package = commands.add_parser("postgresql-package", help="Create PostgreSQL runtime and development archives")
    postgres_package.add_argument("install_prefix")
    postgres_package.add_argument("dependency_prefix")
    postgres_package.add_argument("output_dir")

    extension_build = commands.add_parser("extension-build", help="Build one extension package")
    extension_build.add_argument("package", choices=SUPPORT["packages"])
    extension_build.add_argument("postgresql_prefix")
    extension_build.add_argument("output_dir")

    archive_check = commands.add_parser("archive-check", help="Validate archive contents and overlaps")
    archive_check.add_argument("archives", nargs="+")

    record = commands.add_parser("build-record", help="Record a produced archive and its selected inputs")
    record.add_argument("component", choices=["postgresql", *SUPPORT["packages"]])
    record.add_argument("archive")
    record.add_argument("output")
    record.add_argument("--revision", required=True)
    record.add_argument("--postgresql-archive")
    record.add_argument("--development-archive")

    runtime_check = commands.add_parser("runtime-check", help="Test extracted archives in a fresh installation")
    runtime_check.add_argument("postgresql_archive")
    runtime_check.add_argument("output_parent")
    runtime_check.add_argument("--package-archive", action="append", default=[], metavar="PACKAGE=ARCHIVE")

    release_check = commands.add_parser("release-check", help="Verify every macOS archive combination")
    release_check.add_argument("postgresql_archive")
    release_check.add_argument("output_dir")
    release_check.add_argument("--package-archive", action="append", default=[], metavar="PACKAGE=ARCHIVE")
    release_check.add_argument("--build-record", action="append", default=[], metavar="COMPONENT=PATH")
    release_check.add_argument("--origin-run", action="append", default=[], metavar="COMPONENT=RUN_ID")

    select_runs = commands.add_parser("select-runs", help="Select build artefacts from explicit workflow runs")
    select_runs.add_argument("output_dir")
    select_runs.add_argument("--run", action="append", required=True, type=int, dest="runs",
                             help="workflow run ID, in selection order")
    select_runs.add_argument("--component", action="append", choices=["postgresql", *SUPPORT["packages"]])
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
    postgres = SUPPORT["postgresql"]
    postgres_recipe = ROOT / "packages" / "postgresql" / target

    if args.command == "postgresql-dependencies":
        run_recipe(postgres_recipe / "build-dependencies.sh", [args.prefix], target)
    elif args.command == "postgresql-build":
        source = postgres["source"]
        run_recipe(
            postgres_recipe / "build.sh",
            [source["url"], source["sha256"], postgres["version"], args.dependency_prefix, args.build_dir, args.install_prefix],
            target,
        )
    elif args.command == "postgresql-package":
        run_recipe(postgres_recipe / "package.sh", [args.install_prefix, args.dependency_prefix, args.output_dir], target)
    elif args.command == "extension-build":
        package = SUPPORT["packages"][args.package]
        if len(package["sources"]) != 1:
            raise SystemExit(f"{args.package} needs a package recipe for its {len(package['sources'])} sources")
        source = package["sources"][0]
        run_recipe(
            ROOT / "packages" / args.package / target / "build.sh",
            [source["url"], source["sha256"], source["version"], args.postgresql_prefix, args.output_dir],
            target,
        )
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
        command = [sys.executable, "-m", "verification.macos.runtime", args.postgresql_archive, args.output_parent]
        for package_archive in args.package_archive:
            command.extend(["--package-archive", package_archive])
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
    elif args.command == "release-check":
        command = [sys.executable, "-m", "verification.macos.release", args.postgresql_archive, args.output_dir]
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
