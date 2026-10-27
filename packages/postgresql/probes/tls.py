#!/usr/bin/env python3
"""Verify packaged PostgreSQL TLS and the built-in sslinfo extension."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile


def run(arguments: list[str], environment: dict[str, str]) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True, check=False, env=environment)
    if result.returncode:
        detail = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        raise RuntimeError(f"{' '.join(arguments)} failed" + (f":\n{detail}" if detail else ""))
    return result.stdout.strip()


def probe(installation: Path, work_parent: Path) -> None:
    bin_dir = installation / "bin"
    binaries = {name: bin_dir / name for name in ("initdb", "pg_ctl", "psql")}
    missing = [str(path) for path in binaries.values() if not path.is_file()]
    if missing:
        raise RuntimeError("missing PostgreSQL binaries: " + ", ".join(missing))
    openssl = Path("/usr/bin/openssl")
    if not openssl.is_file():
        raise RuntimeError("system OpenSSL was not found at /usr/bin/openssl")

    user = getpass.getuser()
    work_parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="pg-tls-", dir=work_parent))
    data, certs, log = temporary / "data", temporary / "certs", temporary / "postgres.log"
    certs.mkdir()
    environment = {
        "HOME": str(Path.home()),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
    }
    started = False
    stopped = False
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]

        run([str(openssl), "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-days", "1", "-nodes",
             "-subj", "/CN=pg-tls-probe-ca", "-keyout", str(certs / "ca.key"),
             "-out", str(certs / "ca.crt")], environment)
        for peer, common_name in (("server", "localhost"), ("client", user)):
            run([str(openssl), "req", "-newkey", "rsa:2048", "-sha256", "-nodes", "-subj",
                 f"/CN={common_name}", "-keyout", str(certs / f"{peer}.key"), "-out",
                 str(certs / f"{peer}.csr")], environment)
            run([str(openssl), "x509", "-req", "-in", str(certs / f"{peer}.csr"), "-CA",
                 str(certs / "ca.crt"), "-CAkey", str(certs / "ca.key"), "-CAcreateserial",
                 "-days", "1", "-sha256", "-out", str(certs / f"{peer}.crt")], environment)
        for key in certs.glob("*.key"):
            key.chmod(0o600)

        run([str(binaries["initdb"]), "-D", str(data), "--no-sync", "--username", user], environment)
        (data / "pg_hba.conf").write_text(
            "local all all trust\n"
            f"hostssl all all 127.0.0.1/32 cert\n",
            encoding="utf-8",
        )
        with (data / "postgresql.conf").open("a", encoding="utf-8") as config:
            config.write(
                f"\nlisten_addresses = '127.0.0.1'\nport = {port}\nssl = on\n"
                f"ssl_cert_file = '{certs / 'server.crt'}'\n"
                f"ssl_key_file = '{certs / 'server.key'}'\n"
                f"ssl_ca_file = '{certs / 'ca.crt'}'\n"
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
            stop = subprocess.run([str(binaries["pg_ctl"]), "-D", str(data), "-m", "fast", "-w", "stop"],
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
    arguments = parser.parse_args()
    try:
        probe(arguments.installation.resolve(), arguments.work_parent.resolve())
    except (OSError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PostgreSQL TLS and sslinfo probes passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
