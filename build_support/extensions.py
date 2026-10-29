"""Prepare an isolated extension workspace and invoke its build script."""

import os
import json
from pathlib import Path
import subprocess
import tempfile

from build_support.metadata import ROOT, load_package
from build_support.sources import extract, prepare_sources, sha256


def prepare_workspace(workspace, development, metadata, cache):
    from build_support.postgresql import prepare_development

    workspace = workspace.resolve()
    development = development.resolve()
    cache = cache.resolve()
    if workspace == cache or workspace in cache.parents:
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


def build_extension(package, target, development, output, workspace=None, cache=None):
    from build_support.bundling import finish_extension

    metadata = load_package(package)
    output = Path(output).resolve()
    if workspace is None:
        output.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix=f"{package}-", dir=output.parent))
    else:
        workspace = Path(workspace).resolve()
    cache = Path(cache).expanduser() if cache else Path.home() / ".cache/pg_binaries/sources"
    development = Path(development).resolve()
    development_input = ({"filename": development.name, "sha256": sha256(development)}
                         if development.is_file() else None)
    workspace = prepare_workspace(workspace, development, metadata, cache)
    os_name, architecture = target.split("-", 1)
    environment = os.environ.copy()
    if os_name == "macos":
        support = json.loads((ROOT / "support.json").read_text())
        environment["MACOSX_DEPLOYMENT_TARGET"] = support["targets"][target]["minimum_os_version"]
        environment["COPYFILE_DISABLE"] = "1"
    subprocess.run(["bash", str(ROOT / "packages" / package / "build.sh"), os_name,
                    architecture, str(workspace)], check=True, env=environment, cwd=ROOT)
    version = subprocess.check_output([str(workspace / "postgresql/bin/pg_config"), "--version"],
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
