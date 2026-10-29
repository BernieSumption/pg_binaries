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


def finish_extension(workspace: Path, target: str, output_dir: Path,
                     package: str, postgres_version: str) -> Path:
    workspace = workspace.resolve()
    payload = workspace / "payload"
    postgres = workspace / "postgresql"
    dependencies = workspace / "build/dependencies"
    dependencies.mkdir(parents=True, exist_ok=True)
    if target.startswith("linux-"):
        environment = os.environ.copy()
        paths = [payload / "lib", payload / "lib/runtime", dependencies / "lib",
                 dependencies / "lib64", postgres / "lib", postgres / "lib/runtime"]
        environment["LD_LIBRARY_PATH"] = ":".join(map(str, paths)) + (
            ":" + environment["LD_LIBRARY_PATH"] if environment.get("LD_LIBRARY_PATH") else "")
        subprocess.run(["bash", str(ROOT / "platforms/linux/bundle-runtime.sh"),
                        str(payload), str(payload / "lib/runtime"), str(postgres), "EXTENSION"],
                       env=environment, check=True)
        subprocess.run(["bash", str(ROOT / "platforms/linux/relocate-runtime.sh"),
                        str(payload), "EXTENSION"], check=True)
    elif target.startswith("macos-"):
        subprocess.run([sys.executable, str(ROOT / "platforms/macos/bundle.py"),
                        str(payload), str(dependencies), "--postgresql-prefix", str(postgres)], check=True)
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
