"""State and locking for local extension build workspaces."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


MARKER = ".pg-binaries-extension-workspace.json"
LOCK = ".pg-binaries-extension-workspace.lock"
KEY_ENVIRONMENT = (
    "CC", "CXX", "AR", "RANLIB", "CFLAGS", "CXXFLAGS", "CPPFLAGS",
    "LDFLAGS", "PG_LDFLAGS", "PKG_CONFIG_PATH", "MACOSX_DEPLOYMENT_TARGET",
    "SDKROOT", "DEVELOPER_DIR", "VSINSTALLDIR", "VCToolsVersion", "WindowsSDKVersion",
    "PG_WINDOWS_TOOLS", "PG_MSYS2_ROOT",
    "ARCHFLAGS", "MAKEFLAGS", "CMAKE_ARGS", "RUSTFLAGS",
    "CARGO_ENCODED_RUSTFLAGS", "CARGO_HOME", "RUSTUP_HOME", "RUSTC_WRAPPER",
    "PATH",
)


class WorkspaceLock:
    def __init__(self, workspace):
        self.path = Path(workspace) / LOCK
        self.descriptor = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            try:
                owner = self.path.read_text().strip() or "unknown"
            except OSError:
                owner = "unknown"
            raise ValueError(
                f"extension workspace is locked by PID {owner}: {self.path.parent}; "
                f"after confirming that process has exited, remove {self.path} to recover"
            ) from exc
        os.write(self.descriptor, f"{os.getpid()}\n".encode())
        return self

    def __exit__(self, *_):
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.path.unlink(missing_ok=True)


def _digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_tree(path):
    path = Path(path)
    if path.is_file():
        return _digest_file(path)
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if "__pycache__" in item.parts or item.suffix == ".pyc" or item.name == ".DS_Store":
            continue
        relative = item.relative_to(path).as_posix()
        digest.update(relative.encode())
        digest.update(str(item.lstat().st_mode & 0o777).encode())
        if item.is_symlink():
            digest.update(b"L" + os.readlink(item).encode())
        elif item.is_file():
            digest.update(b"F" + bytes.fromhex(_digest_file(item)))
        elif item.is_dir():
            digest.update(b"D")
    return digest.hexdigest()


def development_identity(path):
    return _digest_tree(path)


def _compiler_identity(environment):
    result = {}
    for name in ("CC", "CXX", "AR", "RANLIB"):
        command = environment.get(name) or {"CC": "cc", "CXX": "c++", "AR": "ar", "RANLIB": "ranlib"}[name]
        executable = command.split()[0]
        resolved = shutil.which(executable, path=environment.get("PATH")) or executable
        version = ""
        try:
            version = subprocess.run([resolved, "--version"], text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, timeout=5, check=False).stdout[:4096]
        except (OSError, subprocess.TimeoutExpired):
            pass
        result[name] = {"path": str(Path(resolved).resolve()) if Path(resolved).exists() else resolved,
                        "version": version}
    dpkg = shutil.which("dpkg-query", path=environment.get("PATH"))
    if dpkg:
        state = subprocess.run([dpkg, "-W", "-f=${binary:Package}=${Version}\\n"],
                               text=True, capture_output=True, check=True)
        result["debian_packages"] = hashlib.sha256(state.stdout.encode()).hexdigest()
    msys = environment.get("PG_MSYS2_ROOT")
    if not msys and environment.get("PG_WINDOWS_TOOLS"):
        msys = str(Path(environment["PG_WINDOWS_TOOLS"]) / "msys64")
    if msys and (pacman := Path(msys) / "usr/bin/pacman.exe").is_file():
        state = subprocess.run([str(pacman), "-Q"], text=True, capture_output=True, check=True)
        result["msys2"] = {"path": str(Path(msys).resolve()),
                           "packages_sha256": hashlib.sha256(state.stdout.encode()).hexdigest()}
    return result


def _hash_files(paths, package_dir):
    digest = hashlib.sha256()
    for path in sorted(paths):
        if "__pycache__" in path.parts or path.suffix == ".pyc" or path.name == ".DS_Store":
            continue
        digest.update(path.relative_to(package_dir).as_posix().encode())
        digest.update(bytes.fromhex(_digest_file(path)))
    return digest.hexdigest()


def recipe_inputs(package_dir, target="linux-arm64"):
    package_dir = Path(package_dir)
    suffix = ".ps1" if target.startswith("windows-") else ".sh"
    dependency_script = package_dir / ("build-dependencies" + suffix)
    dependency_files = [dependency_script] if dependency_script.is_file() else []
    internal = package_dir / "internal"
    dependency_directory = internal / "dependencies"
    if dependency_directory.is_dir():
        dependency_files.extend(p for p in dependency_directory.rglob("*") if p.is_file())
    main_files = [package_dir / ("build" + suffix)]
    if internal.is_dir():
        main_files.extend(p for p in internal.rglob("*")
                          if p.is_file() and (not p.relative_to(internal).parts or
                                              p.relative_to(internal).parts[0] != "dependencies"))
    return _hash_files(main_files, package_dir), _hash_files(dependency_files, package_dir) if dependency_files else None


def _key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def iteration_keys(package, target, metadata, development, package_dir, environment):
    main_recipe, dependency_recipe = recipe_inputs(package_dir, target)
    shared = {
        "package": package,
        "target": target,
        "sources": {name: source["sha256"] for name, source in metadata["sources"].items()},
    }
    compiler = _compiler_identity(environment)
    settings = {name: environment.get(name, "") for name in KEY_ENVIRONMENT}
    context_key = _key({"target": target, "development": str(development),
                        "compiler": compiler, "settings": settings})
    dependency_key = None
    if dependency_recipe is not None:
        dependency_key = _key({**shared, "context": context_key, "recipe": dependency_recipe})
    return {
        "source_key": _key(shared["sources"]),
        "context_key": context_key,
        "dependency_key": dependency_key,
        "main_key": _key({**shared, "recipe": main_recipe}),
    }


def prepare_reused_workspace(workspace, package, target, keys):
    workspace = Path(workspace)
    marker_path = workspace / MARKER
    if not workspace.exists():
        workspace.mkdir(parents=True)
    if not workspace.is_dir():
        raise ValueError(f"extension workspace is not a directory: {workspace}")
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid extension workspace marker: {marker_path}") from exc
        if marker.get("package") != package or marker.get("target") != target:
            raise ValueError(f"extension workspace belongs to {marker.get('package')} {marker.get('target')}")
    elif any(item.name != LOCK for item in workspace.iterdir()):
        raise ValueError(f"extension workspace is not an extension build workspace: {workspace}")
    else:
        marker = {"package": package, "target": target}

    old = marker
    if old.get("source_key") != keys["source_key"] or old.get("context_key") != keys["context_key"]:
        shutil.rmtree(workspace / "sources", ignore_errors=True)
        shutil.rmtree(workspace / "build", ignore_errors=True)
    elif old.get("dependency_success_key") != keys["dependency_key"]:
        shutil.rmtree(workspace / "sources", ignore_errors=True)
        shutil.rmtree(workspace / "build", ignore_errors=True)
    elif old.get("main_key") != keys["main_key"]:
        shutil.rmtree(workspace / "sources", ignore_errors=True)
        build = workspace / "build"
        if build.exists():
            retained = {"target", "pgrx"}
            if keys["dependency_key"] is not None:
                retained.add("dependencies")
            for child in build.iterdir():
                if child.name not in retained:
                    shutil.rmtree(child) if child.is_dir() else child.unlink()
    (workspace / "sources").mkdir(exist_ok=True)
    (workspace / "build").mkdir(exist_ok=True)
    shutil.rmtree(workspace / "payload", ignore_errors=True)
    (workspace / "payload").mkdir()
    shutil.rmtree(workspace / "build/stage", ignore_errors=True)
    marker["source_key"] = keys["source_key"]
    marker["context_key"] = keys["context_key"]
    marker["main_key"] = keys["main_key"]
    marker_path.write_text(json.dumps(marker, indent=2) + "\n")
    return marker


def record_dependency_success(workspace, key):
    path = Path(workspace) / MARKER
    marker = json.loads(path.read_text())
    marker["dependency_success_key"] = key
    path.write_text(json.dumps(marker, indent=2) + "\n")
