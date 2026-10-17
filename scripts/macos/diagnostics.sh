#!/usr/bin/env bash
set -euo pipefail

archives=$(cd "${1:?usage: diagnostics.sh ARCHIVE_DIRECTORY [ARCHITECTURE] [POSTGRESQL_VERSION] [PGVECTOR_VERSION] [REPORT.json]}" && pwd)
architecture=${2:-$(uname -m)}
pg_version=${3:-18.6}
vector_version=${4:-0.8.7}
report=${5:-"$archives/macos-diagnostics-${pg_version}-${architecture}.json"}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported macOS architecture: $architecture" >&2; exit 2 ;; esac
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "Diagnostics require native macOS $architecture" >&2
  exit 2
fi

pg_name="postgresql-${pg_version}-macos-${architecture}.tar.gz"
vector_name="pgvector-${vector_version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
pg_archive="$archives/$pg_name"
vector_archive="$archives/$vector_name"
for file in "$pg_archive" "$vector_archive"; do
  test -s "$file" || { echo "Missing diagnostic input: $file" >&2; exit 2; }
done
cd "$archives"
shasum -a 256 -c "$pg_name.sha256" "$vector_name.sha256"
work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/pg-macos-diagnostics.XXXXXX")
data=
pg_ctl=
cleanup() {
  if [[ -n $data && -n $pg_ctl ]]; then
    "$pg_ctl" -D "$data" -m immediate stop >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/system" "$work/server" "$(dirname "$report")"

tar -xzf "$pg_archive" -C "$work/system"
tar -xzf "$vector_archive" -C "$work/system"
root="$work/system/postgresql"
test -x "$root/bin/postgres"

otool_output=$(otool -L "$root/bin/postgres")
missing_dylib=$(printf '%s\n' "$otool_output" | sed -nE 's/^[[:space:]]+(@loader_path\/[^[:space:]]+\.dylib).*/\1/p' | head -n 1)
if [[ -z $missing_dylib ]]; then
  echo "Could not identify a bundled @loader_path dylib in postgres dependencies" >&2
  exit 1
fi
missing_path=$(python3 - "$root/bin/postgres" "$missing_dylib" <<'PY'
import pathlib, sys
binary = pathlib.Path(sys.argv[1])
dependency = sys.argv[2]
path = (binary.parent / dependency.removeprefix('@loader_path/')).resolve()
if not path.is_relative_to(binary.parent.parent):
    raise SystemExit('diagnostic dependency escapes the extracted archive')
print(path)
PY
)
test -s "$missing_path" || { echo "Expected bundled dependency missing: $missing_path" >&2; exit 1; }
mv "$missing_path" "$missing_path.diagnostic-hidden"
system_started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
set +e
system_output=$(env DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH= "$root/bin/postgres" --version 2>&1)
system_status=$?
set -e
system_finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if [[ $system_status -eq 0 ]] || ! grep -Eqi 'Library not loaded|image not found|dyld' <<<"$system_output"; then
  echo "System failure did not produce the expected macOS loader error" >&2
  printf '%s\n' "$system_output" >&2
  exit 1
fi

# Re-extract pristine archive bytes for the PostgreSQL error case.
rm -rf "$work/server"
mkdir -p "$work/server"
tar -xzf "$pg_archive" -C "$work/server"
tar -xzf "$vector_archive" -C "$work/server"
root="$work/server/postgresql"
data="$work/server/data"
socket="$work/server/socket"
log="$work/server/server.log"
mkdir -p "$socket"
"$root/bin/initdb" -D "$data" --encoding=UTF8 --locale=C --no-instructions > "$work/server/initdb.log" 2>&1
"$root/bin/pg_ctl" -D "$data" -o "-k $socket -p 55439 -h ''" -l "$log" -w start >/dev/null
pg_ctl="$root/bin/pg_ctl"
server_failure_started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
set +e
client_output=$(env DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH= "$root/bin/psql" -X -v ON_ERROR_STOP=1 -h "$socket" -p 55439 -d postgres -c 'SELECT 1 / 0;' 2>&1)
client_status=$?
set -e
server_failure_finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$root/bin/pg_ctl" -D "$data" -m fast -w stop >/dev/null
data=
pg_ctl=
if [[ $client_status -eq 0 ]] || ! grep -q 'ERROR:  division by zero' "$log"; then
  echo "PostgreSQL failure did not produce the expected server log entry" >&2
  cat "$log" >&2
  exit 1
fi

PG_DIAG_REPORT="$report" PG_DIAG_ARCHIVE_DIR="$archives" PG_DIAG_PG_NAME="$pg_name" \
PG_DIAG_VECTOR_NAME="$vector_name" \
PG_DIAG_SYSTEM_OUTPUT="$system_output" PG_DIAG_SYSTEM_STATUS="$system_status" \
PG_DIAG_SYSTEM_STARTED="$system_started" PG_DIAG_SYSTEM_FINISHED="$system_finished" \
PG_DIAG_MISSING_DYLIB="$missing_path" PG_DIAG_OTOOL="$otool_output" \
PG_DIAG_CLIENT_OUTPUT="$client_output" PG_DIAG_CLIENT_STATUS="$client_status" \
PG_DIAG_SERVER_STARTED="$server_failure_started" PG_DIAG_SERVER_FINISHED="$server_failure_finished" \
PG_DIAG_SERVER_LOG="$log" PG_DIAG_ROOT="$root" PG_DIAG_PG_VERSION="$pg_version" \
PG_DIAG_VECTOR_VERSION="$vector_version" PG_DIAG_ARCH="$architecture" \
PG_DIAG_REPORT_PATH="$report" python3 - <<'PY'
import hashlib, json, os, platform, shutil, subprocess
from pathlib import Path

def command_version(*args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else "unavailable"

archive_dir = Path(os.environ["PG_DIAG_ARCHIVE_DIR"])
hashes = {}
for name in (os.environ["PG_DIAG_PG_NAME"], os.environ["PG_DIAG_VECTOR_NAME"]):
    digest = hashlib.sha256((archive_dir / name).read_bytes()).hexdigest()
    hashes[name] = digest
metadata = json.loads((Path(os.environ["PG_DIAG_ROOT"]) / "manifest.json").read_text())
vector_metadata = json.loads((Path(os.environ["PG_DIAG_ROOT"]).parent / "metadata.json").read_text())
if metadata.get("build_id") != vector_metadata.get("build_id") or not metadata.get("build_id"):
    raise SystemExit("archive metadata has missing or inconsistent build identifiers")
env_names = ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH",
             "DYLD_FALLBACK_FRAMEWORK_PATH", "PGDATA", "PGSYSCONFDIR")
record = {
    "schema_version": 1,
    "platform": "macos",
    "architecture": os.environ["PG_DIAG_ARCH"],
    "os_version": command_version("sw_vers", "-productVersion"),
    "kernel": platform.release(),
    "postgresql_version": os.environ["PG_DIAG_PG_VERSION"],
    "pgvector_version": os.environ["PG_DIAG_VECTOR_VERSION"],
    "build_id": metadata["build_id"],
    "source_revision": metadata.get("source_revision"),
    "inventory_revision": None,
    "archive_urls": None,
    "archives": hashes,
    "package_metadata": {"postgresql": metadata, "pgvector": vector_metadata},
    "inspection_tool_versions": {
        "apple_toolchain": command_version("xcodebuild", "-version"),
        "otool_path": shutil.which("otool"),
        "postgres": command_version(str(Path(os.environ["PG_DIAG_ROOT"]) / "bin/postgres"), "--version"),
    },
    "lookup_environment": {name: os.environ.get(name, "") for name in env_names},
    "system_failure": {
        "kind": "missing-bundled-dylib", "executable": str(Path(os.environ["PG_DIAG_ROOT"]) / "bin/postgres"),
        "missing_library": os.environ["PG_DIAG_MISSING_DYLIB"],
        "started_at_utc": os.environ["PG_DIAG_SYSTEM_STARTED"],
        "finished_at_utc": os.environ["PG_DIAG_SYSTEM_FINISHED"],
        "command": "postgres --version", "working_directory": os.getcwd(),
        "exit_code": int(os.environ["PG_DIAG_SYSTEM_STATUS"]),
        "loader_output": os.environ["PG_DIAG_SYSTEM_OUTPUT"],
        "otool_dependencies": os.environ["PG_DIAG_OTOOL"],
    },
    "postgresql_failure": {
        "kind": "server-error", "command": "psql -X -v ON_ERROR_STOP=1 -c 'SELECT 1 / 0;'",
        "started_at_utc": os.environ["PG_DIAG_SERVER_STARTED"],
        "finished_at_utc": os.environ["PG_DIAG_SERVER_FINISHED"],
        "working_directory": os.getcwd(),
        "server_start_command": "pg_ctl -D <data-directory> -o <socket-options> -l <server-log> -w start",
        "server_log_path": os.environ["PG_DIAG_SERVER_LOG"],
        "exit_code": int(os.environ["PG_DIAG_CLIENT_STATUS"]),
        "client_output": os.environ["PG_DIAG_CLIENT_OUTPUT"],
        "server_log": Path(os.environ["PG_DIAG_SERVER_LOG"]).read_text(errors="replace"),
    },
}
if not record["system_failure"]["loader_output"] or not record["postgresql_failure"]["server_log"]:
    raise SystemExit("diagnostic report lacks required failure evidence")
Path(os.environ["PG_DIAG_REPORT_PATH"]).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
PY
echo "macOS failure diagnostics written to $report"
