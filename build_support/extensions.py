"""Prepare an isolated extension workspace and invoke its build script."""

import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_support.metadata import ROOT, load_package
from build_support.sources import extract, prepare_sources, sha256
from build_support.iteration import (WorkspaceLock, development_identity,
                                     iteration_keys, prepare_reused_workspace,
                                     record_dependency_success)


def prepare_workspace(workspace, development, metadata, cache):
    from build_support.postgresql import prepare_development

    workspace = workspace.resolve()
    if any(character.isspace() for character in str(workspace)):
        raise ValueError("PostgreSQL build workspaces must have paths without whitespace")
    development = development.resolve()
    cache = cache.resolve()
    if workspace == cache or workspace in cache.parents or cache in workspace.parents:
        raise ValueError("source cache must be outside the build workspace")
    if workspace == development or workspace in development.parents or (development.is_dir() and development in workspace.parents):
        raise ValueError("development input must be outside the build workspace")
    workspace.mkdir(parents=True, exist_ok=True)
    if any(workspace.iterdir()):
        raise ValueError(f"build workspace must be empty: {workspace}")
    prepare_sources(metadata["sources"], workspace / "sources", cache)
    if development.is_dir():
        prepare_development(development, workspace / "postgresql")
    else:
        with tempfile.TemporaryDirectory(prefix="postgresql-development-") as temporary:
            extracted = Path(temporary) / "installation"
            extract(development, extracted)
            prefix = extracted / "postgresql" if (extracted / "postgresql").is_dir() else extracted
            prepare_development(prefix, workspace / "postgresql")
    (workspace / "build").mkdir()
    (workspace / "payload").mkdir()
    return workspace


def _prepare_postgresql(development, workspace):
    from build_support.postgresql import prepare_development

    destination = workspace / "postgresql"
    shutil.rmtree(destination, ignore_errors=True)
    if development.is_dir():
        prepare_development(development, destination)
    else:
        with tempfile.TemporaryDirectory(prefix="postgresql-development-") as temporary:
            extracted = Path(temporary) / "installation"
            extract(development, extracted)
            prefix = extracted / "postgresql" if (extracted / "postgresql").is_dir() else extracted
            prepare_development(prefix, destination)


def build_extension(package, target, development, output, workspace=None, cache=None, reuse_workspace=False):
    from build_support.bundling import finish_extension

    metadata = load_package(package)
    output = Path(output).resolve()
    reuse = reuse_workspace
    if reuse:
        if workspace is None:
            raise ValueError("--reuse-workspace requires --workspace")
        workspace = Path(workspace).expanduser()
        if not workspace.is_absolute():
            raise ValueError("--reuse-workspace requires an absolute --workspace path")
        workspace = workspace.resolve()
    else:
        if workspace is None:
            output.mkdir(parents=True, exist_ok=True)
            workspace = Path(tempfile.mkdtemp(prefix=f"{package}-", dir=None if os.name == "nt" else "/tmp"))
        else:
            workspace = Path(workspace).resolve()
    cache = Path(cache).expanduser() if cache else Path.home() / ".cache/pg_binaries/sources"
    development = Path(development).resolve()
    if any(character.isspace() for character in str(workspace)):
        raise ValueError("PostgreSQL build workspaces must have paths without whitespace")
    if reuse and (output == workspace or workspace in output.parents):
        raise ValueError("reused workspace must be outside the output directory")
    cache = cache.resolve()
    if workspace == cache or workspace in cache.parents or cache in workspace.parents:
        raise ValueError("source cache must be outside the build workspace")
    if workspace == development or workspace in development.parents or (development.is_dir() and development in workspace.parents):
        raise ValueError("development input must be outside the build workspace")
    development_input = ({"filename": development.name, "sha256": sha256(development)}
                         if development.is_file() else None)
    os_name, architecture = target.split("-", 1)
    environment = os.environ.copy()
    if os_name == "macos":
        support = json.loads((ROOT / "support.json").read_text())
        environment["MACOSX_DEPLOYMENT_TARGET"] = support["targets"][target]["minimum_os_version"]
        environment["COPYFILE_DISABLE"] = "1"
        environment["PG_LDFLAGS"] = "-Wl,-headerpad_max_install_names " + environment.get("PG_LDFLAGS", "")
    package_dir = ROOT / "packages" / package
    suffix = ".ps1" if os_name == "windows" else ".sh"
    command = (["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File"]
               if os_name == "windows" else ["bash"])

    def run():
        if reuse:
            keys = iteration_keys(package, target, metadata, development_identity(development),
                                 package_dir, environment)
            prepare_reused_workspace(workspace, package, target, keys)
            for source_id in metadata["sources"]:
                if not (workspace / "sources" / source_id).is_dir():
                    shutil.rmtree(workspace / "sources")
                    prepare_sources(metadata["sources"], workspace / "sources", cache)
                    break
            _prepare_postgresql(development, workspace)
        else:
            prepare_workspace(workspace, development, metadata, cache)

        dependency_script = package_dir / ("build-dependencies" + suffix)
        if dependency_script.is_file():
            cached_dependency_key = None
            if reuse:
                marker = json.loads((workspace / ".pg-binaries-extension-workspace.json").read_text())
                cached_dependency_key = marker.get("dependency_success_key")
            if not reuse or cached_dependency_key != keys["dependency_key"]:
                subprocess.run([*command, str(dependency_script), os_name, architecture, str(workspace)],
                               check=True, env=environment, cwd=ROOT)
                if reuse:
                    record_dependency_success(workspace, keys["dependency_key"])
        subprocess.run([*command, str(package_dir / ("build" + suffix)), os_name,
                        architecture, str(workspace)], check=True, env=environment, cwd=ROOT)
        executable = "pg_config.exe" if os_name == "windows" else "pg_config"
        version = subprocess.check_output([str(workspace / "postgresql/bin" / executable), "--version"],
                                          text=True).strip().removeprefix("PostgreSQL ")
        paths = json.loads((workspace / "postgresql/share/pg_build_paths.json").read_text())
        runtime = paths["runtime_archive"]
        archive = finish_extension(workspace, target, output, package, version)
        manifest = {
            "package": package, "postgresql_version": version,
            "postgresql_archive": runtime,
            "archive": {"filename": archive.name, "sha256": sha256(archive)},
        }
        if development_input is not None:
            manifest["postgresql_development_archive"] = development_input
        (output / "extension-build.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return archive

    if reuse:
        with WorkspaceLock(workspace):
            return run()
    return run()
