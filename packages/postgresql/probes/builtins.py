#!/usr/bin/env python3
"""Verify PostgreSQL's source-selected built-in SQL extensions in an installation."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


def run(arguments: list[str], environment: dict[str, str]) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True, check=False, env=environment)
    if result.returncode:
        raise RuntimeError(f"{' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def expected_extensions(source_archive: Path) -> set[str]:
    """Read contrib control names from PostgreSQL source, excluding disabled languages."""
    with tarfile.open(source_archive, "r:gz") as archive:
        names = {
            Path(member.name).name.removesuffix(".control")
            for member in archive.getmembers()
            if member.isfile() and "/contrib/" in member.name and member.name.endswith(".control")
        }
        names.update(
            Path(member.name).name.removesuffix(".control")
            for member in archive.getmembers()
            if member.isfile() and "/src/pl/" in member.name and member.name.endswith(".control")
        )
    return {name for name in names if "plperl" not in name and "plpython" not in name
            and name not in {"pltcl", "pltclu"}}


def probe(installation: Path, source_archive: Path, work_parent: Path) -> list[str]:
    extension_dir = installation / "share/postgresql/extension"
    packaged = {path.name.removesuffix(".control") for path in extension_dir.glob("*.control")}
    expected = expected_extensions(source_archive)
    failures: list[str] = []
    if packaged != expected:
        failures.append("built-in control files differ from source: "
                        f"missing={sorted(expected - packaged)}, unexpected={sorted(packaged - expected)}")
        return failures

    bin_dir = installation / "bin"
    binaries = {name: bin_dir / name for name in ("initdb", "pg_ctl", "psql")}
    missing = [str(path) for path in binaries.values() if not path.is_file()]
    if missing:
        raise RuntimeError("missing PostgreSQL binaries: " + ", ".join(missing))
    work_parent.mkdir(parents=True, exist_ok=True)
    from tempfile import mkdtemp
    temporary = Path(mkdtemp(prefix="pg-builtins-", dir=work_parent))
    data, socket, log = temporary / "data", temporary / "socket", temporary / "postgres.log"
    socket.mkdir()
    environment = {
        "HOME": str(Path.home()),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "PGHOST": str(socket), "PGPORT": "5432", "PGUSER": getpass.getuser(),
    }
    started = False
    stopped = False
    try:
        run([str(binaries["initdb"]), "-D", str(data), "--no-sync"], environment)
        with (data / "postgresql.conf").open("a", encoding="utf-8") as config:
            config.write(f"\nunix_socket_directories = '{socket}'\nlisten_addresses = ''\n"
                         "shared_preload_libraries = 'pg_stat_statements'\nwal_level = logical\n")
        run([str(binaries["pg_ctl"]), "-D", str(data), "-l", str(log), "-w", "start"], environment)
        started = True
        psql = [str(binaries["psql"]), "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", "postgres"]
        for name in sorted(expected):
            try:
                run([*psql, "-c", f'CREATE EXTENSION IF NOT EXISTS "{name}"'], environment)
                present = run([*psql, "-c", f"SELECT count(*) = 1 FROM pg_extension WHERE extname = '{name}'"], environment)
                if present != "t":
                    failures.append(f"{name}: CREATE EXTENSION did not register the extension")
            except RuntimeError as error:
                failures.append(f"{name}: {error}")
        # unaccent's dictionary data is opened on use, so exercise a packaged data file.
        try:
            value = run([*psql, "-c", "SELECT unaccent('Hôtel')"], environment)
            if value != "Hotel":
                failures.append(f"unaccent data probe returned {value!r}, expected 'Hotel'")
        except RuntimeError as error:
            failures.append(f"unaccent data probe failed: {error}")
        fixture = temporary / "file_fdw.csv"
        fixture.write_text("42,hello\n", encoding="utf-8")
        for filename in ("builtin_ops_a_l.sql", "builtin_ops_m_z.sql", "builtin_ops_remaining.sql"):
            script = Path(__file__).with_name(filename)
            try:
                output = run([*psql, "-v", f"fixture_path={fixture}", "-f", str(script)], environment)
                if filename == "builtin_ops_remaining.sql":
                    payload = '"builtin_tcn_remaining",I,"id"=\'91\''
                    if 'Asynchronous notification "tcn"' not in output or payload not in output:
                        failures.append("tcn probe did not receive its notification payload")
            except RuntimeError as error:
                failures.append(f"{filename}: {error}")
    finally:
        if started:
            try:
                run([str(binaries["pg_ctl"]), "-D", str(data), "-m", "fast", "-w", "stop"], environment)
                stopped = True
            except RuntimeError as error:
                failures.append(f"could not stop built-in-test server: {error}")
        if stopped:
            shutil.rmtree(data)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installation", type=Path, help="extracted postgresql/ installation")
    parser.add_argument("source_archive", type=Path, help="selected PostgreSQL source archive")
    parser.add_argument("work_parent", type=Path, help="directory for a temporary database cluster")
    arguments = parser.parse_args()
    try:
        failures = probe(arguments.installation.resolve(), arguments.source_archive.resolve(), arguments.work_parent.resolve())
    except (OSError, RuntimeError, tarfile.TarError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if not failures:
        print("PostgreSQL built-in extension probes passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
