"""Package PostgreSQL and prepare private development installations."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

from build_support.sources import sha256


ROOT = Path(__file__).resolve().parents[1]
PATHS_FILE = "share/pg_build_paths.json"


def built_version(prefix):
    prefix = Path(prefix)
    output = subprocess.check_output([str(prefix / "bin/pg_config"), "--version"], text=True).strip()
    match = re.fullmatch(r"PostgreSQL ([0-9][a-zA-Z0-9._-]*)", output)
    if not match:
        raise ValueError(f"unexpected PostgreSQL version: {output!r}")
    return match.group(1)


def _copy(source, destination):
    shutil.copytree(source, destination, symlinks=True)


def _archive(prefix, destination):
    with tarfile.open(destination, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        archive.add(prefix, arcname="postgresql")
    checksum = sha256(destination)
    destination.with_name(destination.name + ".sha256").write_text(f"{checksum}  {destination.name}\n")
    return {"filename": destination.name, "sha256": checksum}


def _normalise_permissions(prefix):
    for directory, _, files in os.walk(prefix):
        Path(directory).chmod(0o755)
        for name in files:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            is_library = ".so" in name or name.endswith(".dylib")
            executable = bool(path.stat().st_mode & 0o111)
            if is_library and not name.startswith("ld-linux"):
                executable = False
            path.chmod(0o755 if executable else 0o644)


def package_postgresql(workspace, target, output_dir):
    workspace, output_dir = Path(workspace).resolve(), Path(output_dir).resolve()
    install = workspace / "postgresql"
    dependencies = workspace / "build/dependencies"
    payload, development = workspace / "payload", workspace / "development"
    version = built_version(install)
    for stage in (payload, development):
        if stage.exists():
            shutil.rmtree(stage)
    _copy(install, payload)
    for relative in ("include", "lib/pgxs"):
        shutil.rmtree(payload / relative, ignore_errors=True)
    (payload / "bin/pg_config").unlink()
    for path in (payload / "lib").glob("*.a"):
        path.unlink()

    os_name, arch = target.split("-", 1)
    if os_name == "linux":
        subprocess.run(["bash", str(ROOT / "packages/postgresql/internal/package-linux-runtime.sh"),
                        str(payload), str(install), arch], check=True)
    elif os_name == "macos":
        subprocess.run(["python3", str(ROOT / "platforms/macos/bundle.py"), str(payload), str(dependencies)], check=True)
    else:
        raise ValueError(f"unsupported PostgreSQL target: {target}")
    (payload / "LICENCE").write_text("See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md\n")
    _normalise_permissions(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime_archive = _archive(payload, output_dir / f"postgresql-{version}-{target}.tar.gz")

    # Start from the runnable payload so tools invoked by extension builds use
    # the same bundled libraries and Linux loader as the published server.
    _copy(payload, development)
    _copy(install / "include", development / "include")
    _copy(install / "lib/pgxs", development / "lib/pgxs")
    for path in (install / "lib").glob("*.a"):
        shutil.copy2(path, development / "lib" / path.name)
    shutil.copy2(install / "bin/pg_config", development / "bin/pg_config.bin")
    if dependencies.is_dir():
        _copy(dependencies, development / "dependencies")
    (development / PATHS_FILE).write_text(json.dumps({
        "postgresql": str(install), "dependencies": str(dependencies),
        "runtime_archive": runtime_archive,
    }) + "\n")
    _write_pg_config_wrapper(development)
    if os_name == "macos":
        subprocess.run(["python3", str(ROOT / "platforms/macos/bundle.py"), str(development), str(dependencies)], check=True)
    else:
        subprocess.run(["patchelf", "--set-rpath", "$ORIGIN/../lib:$ORIGIN/../lib/runtime", str(development / "bin/pg_config.bin")], check=True)
    _normalise_permissions(development)

    record = {
        "version": version,
        "archive": runtime_archive,
        "development_archive": _archive(development, output_dir / f"postgresql-development-{version}-{target}.tar.gz"),
    }
    (output_dir / "postgresql-build.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def _write_pg_config_wrapper(prefix):
    wrapper = prefix / "bin/pg_config"
    wrapper.write_text('''#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import sys

prefix = Path(__file__).resolve().parents[1]
original = json.loads((prefix / "share/pg_build_paths.json").read_text())
result = subprocess.run([str(prefix / "bin/pg_config.bin"), *sys.argv[1:]], stdout=subprocess.PIPE)
output = result.stdout.decode()
for key, destination in (("dependencies", prefix / "dependencies"), ("postgresql", prefix)):
    output = output.replace(original[key], str(destination))
sys.stdout.write(output)
sys.exit(result.returncode)
''')
    wrapper.chmod(0o755)


def prepare_development(source_prefix, destination):
    source_prefix, destination = Path(source_prefix).resolve(), Path(destination).resolve()
    if source_prefix == destination or source_prefix in destination.parents or destination in source_prefix.parents:
        raise ValueError("development input and private copy must not overlap")
    original = json.loads((source_prefix / PATHS_FILE).read_text())
    _copy(source_prefix, destination)
    replacements = ((str(source_prefix / "dependencies"), str(destination / "dependencies")),
                    (original["dependencies"], str(destination / "dependencies")),
                    (str(source_prefix), str(destination)),
                    (original["postgresql"], str(destination)))
    for path in destination.rglob("*"):
        if not path.is_file() or path.is_symlink() or path == destination / PATHS_FILE:
            continue
        if not (path.name.startswith("Makefile") or path.suffix in (".mk", ".pc", ".la") or path.name.endswith("-config")):
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        updated = text
        for before, after in replacements:
            updated = updated.replace(before, after)
        if updated != text:
            path.write_text(updated)
    _write_pg_config_wrapper(destination)
