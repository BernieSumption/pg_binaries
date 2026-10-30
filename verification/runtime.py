#!/usr/bin/env python3
"""Smoke-test extracted PostgreSQL and selected extension packages in a clean environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from typing import Any, Callable
import urllib.request
import uuid

from verification.archive import read_archive, validate_archives
from verification.dependency_symbols import CHECK_NAME, IsolationError, require_isolation
from build_support.metadata import load_package, packages as package_metadata
from packages.postgresql.probes.builtins import probe as probe_builtins
from packages.postgresql.probes.capabilities import probe as probe_capabilities
from verification.macos.static import inspect as inspect_macho
from verification.linux.static import inspect as inspect_elf
from packages.postgresql.probes.tls import probe as probe_tls


ROOT = Path(__file__).resolve().parents[1]
SUPPORT = json.loads((ROOT / "support.json").read_text(encoding="utf-8"))
PACKAGES = package_metadata()


def record_versions(report: dict, checks: list[dict], expected_extensions: set[str], expected_postgres: str) -> None:
    postgres_checks = [item for item in checks if item["name"] == "PostgreSQL version" and item["outcome"] == "passed"]
    if len(postgres_checks) != 1 or postgres_checks[0].get("version") != expected_postgres:
        raise RuntimeError("packaged PostgreSQL version does not match its build record")
    version = postgres_checks[0]["version"]
    if report["postgresql_version"] not in (None, version):
        raise RuntimeError("PostgreSQL version differs between verification combinations")
    versions = {}
    for item in checks:
        if item["name"] == "SQL probes" and item["outcome"] == "passed":
            versions.update(item.get("extension_versions", {}))
    if set(versions) != expected_extensions:
        raise RuntimeError("verified SQL extension versions do not match the selected extensions")
    for name, value in versions.items():
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"invalid verified SQL extension version for {name}")
        if name in report["extension_versions"] and report["extension_versions"][name] != value:
            raise RuntimeError(f"SQL extension version differs between combinations: {name}")
    report["postgresql_version"] = version
    report["extension_versions"].update(versions)


def check(results: list[dict[str, str | None]], name: str,
          operation: Callable[[], Any]) -> tuple[bool, Any]:
    try:
        value = operation()
    except Exception as error:
        results.append({"name": name, "outcome": "failed", "reason": str(error)})
        if isinstance(error, IsolationError):
            results[-1]["details"] = error.details
        return False, None
    results.append({"name": name, "outcome": "passed", "reason": None})
    return True, value


def skipped(results: list[dict[str, str | None]], name: str, reason: str) -> None:
    results.append({"name": name, "outcome": "not_run", "reason": reason})


def not_applicable(results: list[dict[str, str | None]], name: str, reason: str) -> None:
    results.append({"name": name, "outcome": "not_applicable", "reason": reason})


def clean_disposable(output: Path, installation_parent: Path, database: Path,
                     results: list[dict[str, str | None]]) -> None:
    if any(output.rglob("postmaster.pid")):
        skipped(results, "cleanup", "a PostgreSQL server may still be running")
        return
    def remove() -> None:
        if installation_parent.exists():
            shutil.rmtree(installation_parent)
        if database.exists():
            shutil.rmtree(database)
    check(results, "cleanup", remove)


def run(args: list[str], environment: dict[str, str]) -> str:
    result = subprocess.run(args, env=environment, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"{' '.join(args)} failed:\n{result.stdout}{result.stderr}")
    return result.stdout


def check_failure_diagnostics(psql: list[str], environment: dict[str, str]) -> None:
    for sql, expected in (
        ("SELECT 1 / 0", "division by zero"),
        ("LOAD '$libdir/spike2_missing_library'", "spike2_missing_library"),
    ):
        result = subprocess.run([*psql, "-c", sql], env=environment, text=True,
                                capture_output=True, check=False)
        message = result.stdout + result.stderr
        if result.returncode == 0 or expected not in message or "ERROR:" not in message:
            raise RuntimeError(f"failed-operation diagnostic is missing for {sql}:\n{message}")


def configuration(packages: list[str]) -> tuple[list[str], dict[str, str]]:
    preloads: set[str] = set()
    paths: dict[str, str] = {}
    for name in packages:
        package = PACKAGES[name]
        configs = [package.get("config", {})]
        configs.extend(extension.get("config", {}) for extension in package["extensions"].values())
        for config in configs:
            preloads.update(config.get("shared_preload_libraries", []))
            for variable, relative in config.get("environment_paths", {}).items():
                previous = paths.setdefault(variable, relative)
                if previous != relative:
                    raise RuntimeError(f"conflicting {variable} paths: {previous} and {relative}")
    return sorted(preloads), paths


def selected_postgresql_source(output: Path) -> Path:
    source = load_package("postgresql")["sources"]["postgresql"]
    destination = output / "postgresql-source.tar.gz"
    digest = hashlib.sha256()
    with urllib.request.urlopen(source["url"], timeout=120) as response, destination.open("wb") as archive:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            archive.write(chunk)
            digest.update(chunk)
    if digest.hexdigest() != source["sha256"]:
        raise RuntimeError("PostgreSQL source archive checksum mismatch during verification")
    return destination


def archive_contents(postgresql_archive: Path, package_archives: dict[str, Path]) -> None:
    contents = read_archive(postgresql_archive)
    for executable in ("initdb", "pg_ctl", "psql", "pg_dump", "pg_restore"):
        path = f"postgresql/bin/{executable}"
        entry = contents.get(path)
        if entry is None or entry.kind not in ("file", "hardlink") or not entry.mode & 0o111:
            raise RuntimeError(f"missing or non-executable PostgreSQL tool in archive: {path}")
    for package, archive_path in package_archives.items():
        package_contents = read_archive(archive_path)
        expected = set(PACKAGES[package]["extensions"])
        prefix = "postgresql/share/extension/"
        actual = {path.removeprefix(prefix).removesuffix(".control")
                  for path, entry in package_contents.items()
                  if path.startswith(prefix) and path.endswith(".control")
                  and "/" not in path[len(prefix):] and entry.kind == "file"}
        if actual != expected:
            raise RuntimeError(f"{package} SQL extensions differ: missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}")


def verify(postgresql_archive: Path, package_archives: dict[str, Path], output: Path,
           target: str = "macos-arm64") -> list[dict[str, str | None]]:
    results: list[dict[str, str | None]] = []
    archives = [postgresql_archive, *package_archives.values()]
    safe, _ = check(results, "archive safety and overlap", lambda: validate_archives(archives))
    if not safe:
        for name in ("archive contents", "extraction", "native libraries", CHECK_NAME, "PostgreSQL version", "configuration",
                     "database startup", "SQL probes", "failed-operation diagnostics",
                     "PostgreSQL capabilities", "PostgreSQL built-ins", "TLS and sslinfo"):
            skipped(results, name, "archive safety check failed")
        return results
    check(results, "archive contents", lambda: archive_contents(postgresql_archive, package_archives))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=False)
    installation_parent = output / "installation with spaces"
    installation_parent.mkdir()
    def extract() -> None:
        for archive_path in archives:
            with tarfile.open(archive_path, "r:gz") as archive:
                archive.extractall(installation_parent)
    extracted, _ = check(results, "extraction", extract)
    if not extracted:
        for name in ("native libraries", CHECK_NAME, "PostgreSQL version", "configuration", "database startup", "SQL probes",
                     "failed-operation diagnostics", "PostgreSQL capabilities",
                     "PostgreSQL built-ins", "TLS and sslinfo"):
            skipped(results, name, "extraction failed")
        clean_disposable(output, installation_parent, output / "database", results)
        return results

    installation = installation_parent / "postgresql"
    def inspect() -> None:
        inspector = inspect_elf if target.startswith("linux-") else inspect_macho
        _, static_failures = inspector(installation, target)
        if static_failures:
            raise RuntimeError(f"native library inspection found {static_failures} issue(s)")
    check(results, "native libraries", inspect)
    owners: dict[str, list[str]] = {}
    for package, archive_path in {"postgresql": postgresql_archive, **package_archives}.items():
        for path in read_archive(archive_path):
            if path.startswith("postgresql/"):
                owners.setdefault(path[len("postgresql/"):], []).append(package)
    isolated, details = check(results, CHECK_NAME, lambda: require_isolation(installation, target, owners))
    if isolated:
        results[-1]["details"] = details
    database = output / "database"
    socket = output / "socket"
    socket.mkdir()
    log = output / "server.log"
    bin_dir = installation / "bin"
    environment = {
        "HOME": str(Path.home()),
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "PGHOST": str(socket),
        "PGPORT": "5432",
    }
    if "TMPDIR" in os.environ:
        environment["TMPDIR"] = os.environ["TMPDIR"]

    def postgres_version() -> str:
        version = run([str(bin_dir / "postgres"), "--version"], environment).strip()
        match = re.fullmatch(r"postgres \(PostgreSQL\) ([0-9][A-Za-z0-9._-]*)", version)
        if not match:
            raise RuntimeError(f"unexpected packaged PostgreSQL version: {version!r}")
        return match.group(1)
    version_ok, version = check(results, "PostgreSQL version", postgres_version)
    if version_ok:
        results[-1]["version"] = version

    selected = list(package_archives)
    def configure() -> list[str]:
        preloads, paths = configuration(selected)
        for variable, relative in paths.items():
            directory = installation / relative
            if not directory.is_dir() or not directory.resolve().is_relative_to(installation.resolve()):
                raise RuntimeError(f"missing packaged {variable} directory: {relative}")
            environment[variable] = str(directory)
        return preloads
    configured, preloads = check(results, "configuration", configure)

    started = False
    try:
        if configured:
            def start() -> None:
                run([str(bin_dir / "initdb"), "-D", str(database), "--no-sync", "--encoding=UTF8"], environment)
                with (database / "postgresql.conf").open("a", encoding="utf-8") as settings:
                    settings.write(f"\nunix_socket_directories = '{socket}'\nlisten_addresses = ''\n")
                    if preloads:
                        settings.write(f"shared_preload_libraries = '{','.join(preloads)}'\n")
                run([str(bin_dir / "pg_ctl"), "-D", str(database), "-l", str(log), "-w", "start"], environment)
            started, _ = check(results, "database startup", start)
        else:
            skipped(results, "database startup", "configuration failed")
        psql = [str(bin_dir / "psql"), "-X", "-v", "ON_ERROR_STOP=1", "-d", "postgres"]
        if not started:
            skipped(results, "SQL probes", "database startup did not succeed")
            skipped(results, "failed-operation diagnostics", "database startup did not succeed")
        elif selected:
            probes_ok, versions = check(results, "SQL probes", lambda: extension_probe_session(selected, output, psql, environment, log))
            if probes_ok:
                results[-1]["extension_versions"] = versions
            check(results, "failed-operation diagnostics", lambda: check_failure_diagnostics(psql, environment))
        else:
            check(results, "SQL probes", lambda: dump_restore_probe(output, bin_dir, psql, environment))
            check(results, "failed-operation diagnostics", lambda: check_failure_diagnostics(psql, environment))
    finally:
        if started:
            check(results, "database shutdown", lambda: run(
                [str(bin_dir / "pg_ctl"), "-D", str(database), "-m", "fast", "-w", "stop"], environment))
    if selected:
        for name in ("PostgreSQL capabilities", "PostgreSQL built-ins", "TLS and sslinfo"):
            not_applicable(results, name, "covered by the PostgreSQL-only combination")
    else:
        def capability_check() -> None:
            failures = probe_capabilities(installation, output / "capabilities")
            if failures:
                raise RuntimeError("\n".join(failures))
        check(results, "PostgreSQL capabilities", capability_check)
        def builtin_check() -> None:
            source_archive = selected_postgresql_source(output)
            failures = probe_builtins(installation, source_archive, output / "builtins")
            if failures:
                raise RuntimeError("\n".join(failures))
        check(results, "PostgreSQL built-ins", builtin_check)
        check(results, "TLS and sslinfo", lambda: probe_tls(installation, output / "tls"))
    clean_disposable(output, installation_parent, database, results)
    return results


def extension_probe_session(selected: list[str], output: Path, psql: list[str],
                            environment: dict[str, str], log: Path) -> dict[str, str]:
    probe_script = output / "extension-probes.sql"
    with probe_script.open("w", encoding="utf-8") as script:
        script.write("\\set ON_ERROR_STOP on\n")
        for package in selected:
            for extension in PACKAGES[package]["extensions"]:
                if not re.fullmatch(r"[a-z][a-z0-9_]*", extension):
                    raise RuntimeError(f"invalid SQL extension name: {extension}")
                probe = ROOT / "packages" / package / "probes" / f"{extension}.sql"
                if not probe.is_file():
                    raise RuntimeError(f"missing SQL probe: {probe.relative_to(ROOT)}")
                script.write(f"CREATE EXTENSION IF NOT EXISTS {extension} CASCADE;\n")
                script.write(probe.read_text(encoding="utf-8"))
                script.write("\n")
    run([*psql, "-f", str(probe_script)], environment)
    if "pgaudit" in selected:
        audit_log = log.read_text(encoding="utf-8")
        for operation in ("CREATE TABLE", "INSERT", "SELECT"):
            if not any("AUDIT: SESSION" in line and operation in line for line in audit_log.splitlines()):
                raise RuntimeError(f"pgAudit server log lacks {operation} audit record")
    expected = {name for package in selected for name in PACKAGES[package]["extensions"]}
    names = ",".join(f"'{name}'" for name in sorted(expected))
    query = f"SELECT json_object_agg(extname, extversion)::text FROM pg_extension WHERE extname IN ({names})"
    versions = json.loads(run([*psql, "-tA", "-c", query], environment))
    if not isinstance(versions, dict) or set(versions) != expected or any(not isinstance(value, str) or not value for value in versions.values()):
        raise RuntimeError(f"installed SQL extension versions do not match declared extensions: {versions!r}")
    return versions


def dump_restore_probe(output: Path, bin_dir: Path, psql: list[str],
                       environment: dict[str, str]) -> None:
    run([*psql, "-c", "CREATE TABLE spike2_smoke (value text); INSERT INTO spike2_smoke VALUES ('seed')"], environment)
    dump = output / "database.dump"
    run([str(bin_dir / "pg_dump"), "-Fc", "-f", str(dump), "postgres"], environment)
    run([*psql, "-c", "CREATE DATABASE spike2_restore"], environment)
    run([str(bin_dir / "pg_restore"), "-d", "spike2_restore", str(dump)], environment)
    value = run([str(bin_dir / "psql"), "-X", "-tA", "-d", "spike2_restore", "-c",
                 "SELECT value FROM spike2_smoke"], environment).strip()
    if value != "seed":
        raise RuntimeError(f"dump and restore returned {value!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("postgresql_archive", type=Path)
    parser.add_argument("output_parent", type=Path)
    parser.add_argument("--target", choices=SUPPORT["targets"], default="macos-arm64")
    parser.add_argument("--package-archive", action="append", default=[], metavar="PACKAGE=ARCHIVE",
                        help="repeat for each extension package to test together")
    arguments = parser.parse_args()
    package_archives: dict[str, Path] = {}
    for selection in arguments.package_archive:
        name, separator, filename = selection.partition("=")
        if not separator or name not in PACKAGES or not filename or name in package_archives:
            parser.error(f"invalid or duplicate package archive: {selection}")
        package_archives[name] = Path(filename)
    label = "all" if len(package_archives) > 1 else next(iter(package_archives), "postgresql")
    output = arguments.output_parent / f"verify-{label}-{uuid.uuid4().hex[:8]}"
    results = verify(arguments.postgresql_archive, package_archives, output, arguments.target)
    output.mkdir(parents=True, exist_ok=True)
    (output / "checks.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(output)
    if any(item["outcome"] in ("failed", "not_run") for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
