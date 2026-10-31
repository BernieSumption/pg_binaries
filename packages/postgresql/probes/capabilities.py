#!/usr/bin/env python3
"""Probe selected PostgreSQL build capabilities using an extracted installation."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


try:
    from .environment import executable, clean_environment, connection
except ImportError:
    from environment import executable, clean_environment, connection


def run(arguments: list[str], *, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, capture_output=True, text=True, check=False, env=environment)


def require_command(arguments: list[str], *, environment: dict[str, str] | None = None) -> str:
    result = run(arguments, environment=environment)
    if result.returncode:
        raise RuntimeError(f"{' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def probe(installation: Path, work_parent: Path) -> list[str]:
    bin_dir = installation / "bin"
    binaries = {name: executable(bin_dir, name) for name in ("initdb", "pg_ctl", "psql", "pg_dump", "pg_restore")}
    missing = [str(path) for path in binaries.values() if not path.is_file()]
    if missing:
        raise RuntimeError("missing PostgreSQL binaries: " + ", ".join(missing))

    failures: list[str] = []
    work_parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="pg-capabilities-", dir=work_parent))
    data = temporary / "data"
    socket_parent = Path("/tmp") if Path("/tmp").is_dir() else Path(tempfile.gettempdir())
    socket = Path(tempfile.mkdtemp(prefix="pgc-", dir=socket_parent))
    log = temporary / "postgres.log"
    environment, connection_settings = connection(bin_dir, socket)

    started = False
    stopped = False
    try:
        require_command([str(binaries["initdb"]), "-D", str(data), "--no-sync", "--encoding=UTF8"], environment=environment)
        with (data / "postgresql.conf").open("a", encoding="utf-8") as config:
            config.write(connection_settings + "ssl = off\n")
        require_command([str(binaries["pg_ctl"]), "-D", str(data), "-l", str(log), "-w", "start"], environment=environment)
        started = True
        psql = [str(binaries["psql"]), "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", "postgres"]

        def sql(label: str, statement: str, expected: str = "t") -> None:
            try:
                actual = require_command([*psql, "-c", statement], environment=environment).splitlines()[-1]
            except (RuntimeError, IndexError) as error:
                failures.append(f"{label} probe failed: {error}")
                return
            if actual != expected:
                failures.append(f"{label} probe returned {actual!r}, expected {expected!r}")

        sql("ICU", "CREATE COLLATION capability_icu (provider = icu, locale = 'en', deterministic = false); "
            "SELECT 'a' < 'b' COLLATE capability_icu")
        sql("XML", "SELECT xml_is_well_formed_document('<root/>') AND "
            "xpath_exists('/root/value[text()=\"ok\"]', xmlparse(document '<root><value>ok</value></root>'))")
        sql("PL/pgSQL", "SELECT EXISTS (SELECT FROM pg_language WHERE lanname = 'plpgsql' AND lanpltrusted)")
        sql("LZ4 column compression", "CREATE TABLE capability_lz4 (value text COMPRESSION lz4); "
            "INSERT INTO capability_lz4 VALUES (repeat('x', 10000)); "
            "SELECT pg_column_compression(value) = 'lz4' FROM capability_lz4")
        sql("Zstandard WAL compression", "SELECT 'zstd' = ANY(enumvals) FROM pg_settings WHERE name = 'wal_compression'")

        xml2 = run([*psql, "-c", "CREATE EXTENSION xml2"], environment=environment)
        if xml2.returncode:
            failures.append(f"XSLT (xml2) extension unavailable: {xml2.stderr.strip()}")
        else:
            sql("XSLT", "SELECT xslt_process('<root><value>ok</value></root>', "
                "'<xsl:stylesheet version=\"1.0\" xmlns:xsl=\"http://www.w3.org/1999/XSL/Transform\">"
                "<xsl:template match=\"/\"><result><xsl:value-of select=\"root/value\"/>"
                "</result></xsl:template></xsl:stylesheet>') LIKE '%<result>ok</result>%'")

        for name, compression in (("zlib", "1"), ("Zstandard", "zstd:1")):
            archive = temporary / f"{name.lower()}-dump"
            if compression == "1":
                args = [str(binaries["pg_dump"]), "-Fc", "-Z", compression, "-f", str(archive), "postgres"]
            else:
                args = [str(binaries["pg_dump"]), "-Fc", f"--compress={compression}", "-f", str(archive), "postgres"]
            dump = run(args, environment=environment)
            if dump.returncode:
                failures.append(f"{name} compressed dump failed: {dump.stderr.strip()}")
            else:
                restored = run([str(binaries["pg_restore"]), "-f", os.devnull, str(archive)], environment=environment)
                if restored.returncode:
                    failures.append(f"{name} compressed dump could not be read by pg_restore: {restored.stderr.strip()}")
    finally:
        if started:
            stop = run([str(binaries["pg_ctl"]), "-D", str(data), "-m", "fast", "-w", "stop"], environment=environment)
            if stop.returncode:
                failures.append(f"could not stop capability-test server: {stop.stderr.strip()}")
            else:
                stopped = True
        if stopped:
            shutil.rmtree(data)
        if stopped or not (data / "postmaster.pid").exists():
            shutil.rmtree(socket)

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installation", type=Path, help="extracted postgresql/ installation")
    parser.add_argument("work_parent", type=Path, help="directory for a temporary database cluster")
    arguments = parser.parse_args()
    try:
        failures = probe(arguments.installation.resolve(), arguments.work_parent.resolve())
    except (OSError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if not failures:
        print("PostgreSQL capability probes passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
