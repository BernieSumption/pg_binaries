#!/usr/bin/env python3
"""Collect native Windows startup diagnostics for a saved PostgreSQL archive."""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from packages.postgresql.probes.environment import clean_environment, connection


def decode(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def run_probe(name: str, command: list[str], environment: dict[str, str], *,
              timeout: int = 60, stdin=None) -> dict:
    item = {"name": name, "command": command, "timeout_seconds": timeout,
            "stdin": "devnull" if stdin is subprocess.DEVNULL else "inherited"}
    try:
        result = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                                encoding="utf-8", errors="replace", capture_output=True,
                                timeout=timeout, check=False, stdin=stdin)
        item.update({"returncode": result.returncode,
                     "returncode_hex": f"0x{result.returncode & 0xffffffff:08x}",
                     "stdout": result.stdout, "stderr": result.stderr})
    except subprocess.TimeoutExpired as error:
        item.update({"timed_out": True, "returncode": None,
                     "stdout": decode(error.stdout), "stderr": decode(error.stderr)})
    except Exception as error:
        item.update({"exception": f"{type(error).__name__}: {error}"})
    return item


def suppress_windows_error_dialogs() -> int | None:
    if os.name != "nt":
        return None
    flags = 0x0001 | 0x0002 | 0x8000
    return int(ctypes.windll.kernel32.SetErrorMode(flags))


def initdb_dependencies(binary: Path, output: Path, environment: dict[str, str]) -> None:
    dumpbin = shutil.which("dumpbin.exe") or shutil.which("dumpbin")
    if not dumpbin:
        (output / "dumpbin-initdb-dependents.txt").write_text(
            "dumpbin was not found in the Visual Studio environment.\n", encoding="utf-8")
    else:
        result = subprocess.run([dumpbin, "/dependents", str(binary)], cwd=ROOT,
                                env=environment, text=True, encoding="utf-8",
                                errors="replace", capture_output=True, check=False)
        (output / "dumpbin-initdb-dependents.txt").write_text(
            f"exit_code={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            encoding="utf-8")
    dlls = sorted({str(path.relative_to(binary.parent)) for path in binary.parent.glob("*.dll")})
    (output / "postgresql-bin-dlls.json").write_text(json.dumps(dlls, indent=2) + "\n", encoding="utf-8")


def application_errors(output: Path, environment: dict[str, str]) -> None:
    executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wevtutil.exe"
    query = "*[System[(EventID=1000 or EventID=1001 or EventID=1026) and TimeCreated[timediff(@SystemTime) <= 3600000]]]"
    if not executable.is_file():
        text = "wevtutil.exe was not found.\n"
    else:
        result = subprocess.run([str(executable), "qe", "Application", f"/q:{query}", "/f:text", "/rd:true", "/c:100"],
                                cwd=ROOT, env=environment, text=True, encoding="utf-8",
                                errors="replace", capture_output=True, check=False)
        blocks = result.stdout.replace("\r\n", "\n").split("\n\n")
        matches = [block for block in blocks if "initdb.exe" in block.lower()]
        text = "\n\n".join(matches) if matches else "No recent Application error event named initdb.exe was found.\n"
        if result.returncode:
            text += f"\nwevtutil exit code: {result.returncode}\n{result.stderr}"
    (output / "application-errors-initdb.txt").write_text(text, encoding="utf-8")



def extraction_acl(paths: list[Path]) -> dict:
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    literals = ",".join("'" + str(path).replace("'", "''") + "'" for path in paths)
    script = ("@(" + literals + ") | ForEach-Object { $acl = Get-Acl -LiteralPath $_; "
              "[pscustomobject]@{ Path = $_; Owner = $acl.Owner; Sddl = $acl.Sddl } } | ConvertTo-Json -Depth 4")
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    process = subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return {"returncode": process.returncode, "stdout": process.stdout, "stderr": process.stderr}


def startup_matrix(archive_path: Path, output: Path, result: dict) -> dict:
    if os.name != "nt":
        raise RuntimeError("the loader matrix requires a native Windows runner")
    kernel = ctypes.windll.kernel32
    initial_mode = int(kernel.GetErrorMode())
    suppressed_mode = 0x8003
    # Match the shared verifier's directory names and reuse exactly the same paths.
    case_root = output.parent / "runtime-check" / "verify-postgresql-00000000"
    extraction = case_root / "installation with spaces"
    binary = extraction / "postgresql/bin/initdb.exe"
    reference_fingerprint = None
    result["matrix"] = []
    result["windows_error_mode_before"] = initial_mode
    try:
        for filter_name in ("fully_trusted", "data"):
            for mode_name, mode in (("original", initial_mode), ("suppressed", suppressed_mode)):
                if case_root.exists():
                    shutil.rmtree(case_root)
                extraction.mkdir(parents=True)
                with tarfile.open(archive_path, "r:gz") as package:
                    package.extractall(extraction, filter=filter_name)
                fingerprint = hashlib.sha256()
                for path in sorted(extraction.rglob("*")):
                    if path.is_file():
                        fingerprint.update(path.relative_to(extraction).as_posix().encode())
                        fingerprint.update(hashlib.sha256(path.read_bytes()).digest())
                fingerprint = fingerprint.hexdigest()
                if reference_fingerprint is None:
                    reference_fingerprint = fingerprint
                environment, _ = connection(binary.parent, case_root / "socket", windows=True)
                item = {"extraction_filter": filter_name, "windows_error_mode": mode,
                        "error_mode_name": mode_name, "binary": str(binary),
                        "data": str(case_root / "database"), "cwd": str(ROOT),
                        "extracted_files_fingerprint": fingerprint,
                        "extracted_files_match_first_case": fingerprint == reference_fingerprint,
                        "acl": extraction_acl([case_root, extraction, binary.parent.parent,
                                               binary.parent, binary, binary.parent / "vcruntime140.dll"])}
                kernel.SetErrorMode(mode)
                item["probes"] = [run_probe(f"{filter_name}:{mode_name}:version", [str(binary), "--version"], environment),
                                  run_probe(f"{filter_name}:{mode_name}:initdb", [str(binary), "-D", str(case_root / "database"),
                                            "--no-sync", "--encoding=UTF8"], environment)]
                item["acl_after"] = extraction_acl([path for path in (case_root, extraction, binary.parent.parent,
                                                                      binary.parent, binary, case_root / "database") if path.exists()])
                result["matrix"].append(item)
                (output / "diagnostics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
                if any(probe.get("timed_out") for probe in item["probes"]):
                    raise RuntimeError("a matrix subprocess timed out; its installation is retained")
    finally:
        kernel.SetErrorMode(initial_mode)
    shutil.rmtree(case_root)
    return result


def diagnose(archive_path: Path, record_path: Path, output: Path, *, matrix_only: bool = False) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    expected = record["archive"]["sha256"].lower()
    digest = hashlib.sha256()
    with archive_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    result = {
        "archive": str(archive_path), "record": str(record_path),
        "record_revision": record.get("git_revision"),
        "record_archive_sha256": expected, "actual_archive_sha256": actual,
        "archive_sha256_matches_record": actual == expected,
        "diagnostics": [],
    }
    if actual != expected:
        raise RuntimeError(f"archive SHA-256 {actual} differs from record {expected}")

    if matrix_only:
        return startup_matrix(archive_path, output, result)

    previous_error_mode = suppress_windows_error_dialogs()
    extraction = output / "extracted distribution with spaces"
    extraction.mkdir()
    with tarfile.open(archive_path, "r:gz") as package:
        package.extractall(extraction, filter="data")
    binary = extraction / "postgresql" / "bin" / "initdb.exe"
    if not binary.is_file():
        raise FileNotFoundError(f"archive did not extract initdb.exe at {binary}")
    bin_dir = binary.parent
    data_root = output / "probe data with spaces"
    data_root.mkdir()
    initdb_dependencies(binary, output, os.environ.copy())

    environments = {
        "runner_environment": os.environ.copy(),
        "distribution_only_path": clean_environment(bin_dir, windows=True),
    }
    operations = (("version", ["--version"]), ("help", ["--help"]))
    for environment_name, environment in environments.items():
        for operation_name, arguments in operations:
            command = [str(binary), *[argument.format(data=data_root / f"{environment_name}-{operation_name}")
                                      for argument in arguments]]
            result["diagnostics"].append(run_probe(
                f"{environment_name}:{operation_name}", command, environment))
    environment = environments["distribution_only_path"]
    for stdin_name, stdin in (("inherited_stdin", None), ("stdin_devnull", subprocess.DEVNULL)):
        data = data_root / stdin_name
        command = [str(binary), "-D", str(data), "--no-sync", "--encoding=UTF8", "--debug"]
        result["diagnostics"].append(run_probe(
            f"distribution_only_path:initdb_{stdin_name}", command, environment, stdin=stdin))
    runtime_environment, _ = connection(bin_dir, output / "unused-socket", windows=True)
    for name, environment in (("clean", environments["distribution_only_path"]),
                              ("runtime_connection", runtime_environment)):
        command = [str(binary), "-D", str(data_root / name), "--no-sync", "--encoding=UTF8"]
        result["diagnostics"].append(run_probe(f"{name}:initdb_without_debug", command, environment))
    application_errors(output, os.environ.copy())
    result["windows_error_mode_before"] = previous_error_mode
    result["initdb_binary"] = str(binary)
    result["packaged_dlls"] = len(list(bin_dir.glob("*.dll")))
    result["notes"] = [
        "The archived PostgreSQL bytes were checked against their original build record.",
        "This diagnostic does not assert that the old build inputs match the current repository pins.",
        "Environment variable values are not recorded.",
    ]
    (output / "diagnostics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--matrix-only", action="store_true", help="isolate extraction ACLs and process error mode at identical verifier paths")
    arguments = parser.parse_args()
    try:
        result = diagnose(arguments.archive, arguments.record, arguments.output, matrix_only=arguments.matrix_only)
    except Exception as error:
        arguments.output.mkdir(parents=True, exist_ok=True)
        (arguments.output / "diagnostic-error.txt").write_text(
            f"{type(error).__name__}: {error}\n", encoding="utf-8")
        raise
    probes = result["diagnostics"] + [probe for case in result.get("matrix", []) for probe in case["probes"]]
    for item in probes:
        print(f"{item['name']}: returncode={item.get('returncode')} "
              f"hex={item.get('returncode_hex')} timed_out={item.get('timed_out', False)}")


if __name__ == "__main__":
    main()
