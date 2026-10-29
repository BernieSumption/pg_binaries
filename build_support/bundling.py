"""Finish extension payloads using the shared platform tools."""

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
LICENCE = "See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md\n"


def _namespace_linux_libraries(payload, directory, package):
    renamed = {}
    for library in directory.iterdir():
        if not library.is_file():
            continue
        name = f"{package}-{library.name}"
        renamed[library.name] = name
        destination = library.with_name(name)
        library.rename(destination)
        subprocess.run(["patchelf", "--set-soname", name, str(destination)], check=True)
    if not renamed:
        return
    for binary in payload.rglob("*"):
        if not binary.is_file() or binary.is_symlink():
            continue
        with binary.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        needed = subprocess.check_output(["patchelf", "--print-needed", str(binary)], text=True).splitlines()
        for dependency in needed:
            if dependency in renamed:
                subprocess.run(["patchelf", "--replace-needed", dependency, renamed[dependency], str(binary)], check=True)


def finish_extension(workspace: Path, target: str, output_dir: Path,
                     package: str, postgres_version: str) -> Path:
    workspace = workspace.resolve()
    payload = workspace / "payload"
    postgres = workspace / "postgresql"
    dependencies = workspace / "build/dependencies"
    dependencies.mkdir(parents=True, exist_ok=True)
    private_name = f"{package}-deps"
    private_libraries = payload / "lib" / private_name
    if target.startswith("linux-"):
        environment = os.environ.copy()
        paths = [payload / "lib", private_libraries, dependencies / "lib",
                 dependencies / "lib64", postgres / "lib", postgres / "lib/runtime"]
        environment["LD_LIBRARY_PATH"] = ":".join(map(str, paths)) + (
            ":" + environment["LD_LIBRARY_PATH"] if environment.get("LD_LIBRARY_PATH") else "")
        subprocess.run(["bash", str(ROOT / "platforms/linux/bundle-runtime.sh"),
                        str(payload), str(private_libraries), str(postgres), "EXTENSION"],
                       env=environment, check=True)
        private_libraries.mkdir(parents=True, exist_ok=True)
        _namespace_linux_libraries(payload, private_libraries, package)
        subprocess.run(["bash", str(ROOT / "platforms/linux/relocate-runtime.sh"),
                        str(payload), "EXTENSION", private_name], check=True)
    elif target.startswith("macos-"):
        subprocess.run([sys.executable, str(ROOT / "platforms/macos/bundle.py"),
                        str(payload), str(dependencies), private_name, "--postgresql-prefix", str(postgres)], check=True)
    else:
        raise ValueError(f"unsupported target: {target}")

    (payload / "LICENCE").write_text(LICENCE, encoding="utf-8")
    for path in payload.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_dir():
            path.chmod(0o755)
        elif path.is_file():
            executable = path.stat().st_mode & 0o111
            library = ".so" in path.name or path.suffix == ".dylib"
            path.chmod(0o755 if executable and not library else 0o644)
    payload.chmod(0o755)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"{package}-postgresql-{postgres_version}-{target}.tar.gz"
    with tempfile.TemporaryDirectory(dir=output_dir) as temporary:
        temporary = Path(temporary)
        staged = temporary / archive.name
        with tarfile.open(staged, "w:gz", format=tarfile.PAX_FORMAT) as tar:
            tar.add(payload, arcname="postgresql")
        digest = hashlib.sha256()
        with staged.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        checksum = temporary / (archive.name + ".sha256")
        checksum.write_text(f"{digest.hexdigest()}  {archive.name}\n", encoding="utf-8")
        staged.replace(archive)
        checksum.replace(Path(str(archive) + ".sha256"))
    return archive
