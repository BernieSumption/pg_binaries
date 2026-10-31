#!/usr/bin/env python3
"""Verify packaged PostgreSQL TLS and the built-in sslinfo extension."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import shutil
import socket
import sys
import tarfile


try:
    from .environment import executable, clean_environment, connection, _probe_scratch_directory
    from .process import run as run_process
except ImportError:
    from environment import executable, clean_environment, connection, _probe_scratch_directory
    from process import run as run_process


def run(arguments: list[str], environment: dict[str, str]) -> str:
    result = run_process(arguments, capture_output=True, text=True, check=False, env=environment)
    if result.returncode:
        detail = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        raise RuntimeError(f"{' '.join(arguments)} failed" + (f":\n{detail}" if detail else ""))
    return result.stdout.strip()


def source_certificates(source_archive: Path, destination: Path) -> None:
    """Read PostgreSQL's public TLS identities from a caller-verified source archive."""
    names = {"server.crt": "server-cn-only+server_ca.crt", "server.key": "server-cn-only.key",
             "client.crt": "client+client_ca.crt", "client.key": "client.key",
             "ca.crt": "root_ca.crt", "server-ca.crt": "root+client_ca.crt"}
    with tarfile.open(source_archive, "r:gz") as archive:
        for output, source in names.items():
            matches = [member for member in archive.getmembers()
                       if member.isfile() and member.name.endswith("/src/test/ssl/ssl/" + source)]
            if len(matches) != 1:
                raise RuntimeError(f"PostgreSQL TLS fixture missing or ambiguous: {source}")
            stream = archive.extractfile(matches[0])
            if stream is None:
                raise RuntimeError(f"cannot read PostgreSQL TLS fixture: {source}")
            (destination / output).write_bytes(stream.read())


def probe(installation: Path, work_parent: Path, source_archive: Path | None = None) -> None:
    bin_dir = installation / "bin"
    binaries = {name: executable(bin_dir, name) for name in ("initdb", "pg_ctl", "psql")}
    missing = [str(path) for path in binaries.values() if not path.is_file()]
    if missing:
        raise RuntimeError("missing PostgreSQL binaries: " + ", ".join(missing))
    openssl = Path(os.environ.get("PG_TEST_OPENSSL", "/usr/bin/openssl"))
    if source_archive is None and not openssl.is_file():
        raise RuntimeError("test OpenSSL was not found; set PG_TEST_OPENSSL to an absolute executable path")

    user = "ssltestuser" if source_archive is not None else getpass.getuser()
    work_parent.mkdir(parents=True, exist_ok=True)
    temporary = _probe_scratch_directory(work_parent, "pg-tls-")
    data, certs, log = temporary / "data", temporary / "certs", temporary / "postgres.log"
    certs.mkdir()
    openssl_config = certs / "openssl.cnf"
    openssl_config.write_text("[req]\ndistinguished_name = dn\n[dn]\n", encoding="utf-8")
    environment = clean_environment(bin_dir)

    started = False
    stopped = False
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]

        if source_archive is not None:
            source_certificates(source_archive, certs)
        else:
            run([str(openssl), "req", "-config", str(openssl_config), "-x509", "-newkey", "rsa:2048", "-sha256", "-days", "1", "-nodes",
                 "-subj", "/CN=pg-tls-probe-ca", "-keyout", str(certs / "ca.key"),
                 "-out", str(certs / "ca.crt")], environment)
            for peer, common_name in (("server", "localhost"), ("client", user)):
                run([str(openssl), "req", "-config", str(openssl_config), "-newkey", "rsa:2048", "-sha256", "-nodes", "-subj",
                     f"/CN={common_name}", "-keyout", str(certs / f"{peer}.key"), "-out",
                     str(certs / f"{peer}.csr")], environment)
                run([str(openssl), "x509", "-req", "-in", str(certs / f"{peer}.csr"), "-CA",
                     str(certs / "ca.crt"), "-CAkey", str(certs / "ca.key"), "-CAcreateserial",
                     "-days", "1", "-sha256", "-out", str(certs / f"{peer}.crt")], environment)
        server_ca = certs / ("server-ca.crt" if source_archive is not None else "ca.crt")
        for key in certs.glob("*.key"):
            key.chmod(0o600)

        run([str(binaries["initdb"]), "-D", str(data), "--no-sync", "--encoding=UTF8", "--username", user], environment)
        (data / "pg_hba.conf").write_text(
            ("" if os.name == "nt" else "local all all trust\n") +
            f"hostssl all all 127.0.0.1/32 cert\n",
            encoding="utf-8",
        )
        with (data / "postgresql.conf").open("a", encoding="utf-8") as config:
            config.write(
                f"\nlisten_addresses = '127.0.0.1'\nport = {port}\nssl = on\n"
                f"ssl_cert_file = '{(certs / 'server.crt').as_posix()}'\n"
                f"ssl_key_file = '{(certs / 'server.key').as_posix()}'\n"
                f"ssl_ca_file = '{server_ca.as_posix()}'\n"
            )
        run([str(binaries["pg_ctl"]), "-D", str(data), "-l", str(log), "-w", "start"], environment)
        started = True
        client_environment = {
            **environment,
            "PGSSLMODE": "verify-ca",
            "PGSSLROOTCERT": str(certs / "ca.crt"),
            "PGSSLCERT": str(certs / "client.crt"),
            "PGSSLKEY": str(certs / "client.key"),
        }
        statement = (
            "CREATE EXTENSION sslinfo; "
            "DO $$ BEGIN IF ssl_is_used() IS DISTINCT FROM true "
            "OR ssl_client_cert_present() IS DISTINCT FROM true "
            "OR ssl_client_dn_field('CN') IS DISTINCT FROM current_user "
            "OR ssl_version() IS NULL OR ssl_cipher() IS NULL THEN "
            "RAISE EXCEPTION 'sslinfo did not report the authenticated TLS connection'; "
            "END IF; END $$"
        )
        run([str(binaries["psql"]), "-X", "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1", "-p",
             str(port), "-U", user, "-d", "postgres", "-c", statement], client_environment)
    finally:
        if started:
            stop = run_process([str(binaries["pg_ctl"]), "-D", str(data), "-m", "fast", "-w", "stop"],
                                  capture_output=True, text=True, check=False, env=environment)
            if stop.returncode:
                stopped = False
                print(f"Could not stop PostgreSQL cleanly; see {log}", file=sys.stderr)
            else:
                stopped = True
        if stopped:
            shutil.rmtree(data, ignore_errors=True)
        else:
            print(f"TLS probe files and PostgreSQL log retained at {temporary}", file=sys.stderr)
    if started and not stopped:
        raise RuntimeError(f"could not stop TLS probe server; see {log}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installation", type=Path, help="extracted postgresql/ installation")
    parser.add_argument("work_parent", type=Path, help="directory for disposable cluster and TLS files")
    parser.add_argument("--source-archive", type=Path, help="checksum-verified PostgreSQL source archive supplying public TLS test identities")
    arguments = parser.parse_args()
    try:
        probe(arguments.installation.resolve(), arguments.work_parent.resolve(), arguments.source_archive)
    except (OSError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PostgreSQL TLS and sslinfo probes passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
