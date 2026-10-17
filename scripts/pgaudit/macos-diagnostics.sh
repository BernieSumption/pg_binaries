#!/usr/bin/env bash
set -euo pipefail

core_archive=${1:?usage: macos-diagnostics.sh CORE_ARCHIVE PGAUDIT_ARCHIVE REPORT.json}
extension_archive=${2:?usage: macos-diagnostics.sh CORE_ARCHIVE PGAUDIT_ARCHIVE REPORT.json}
report=${3:?usage: macos-diagnostics.sh CORE_ARCHIVE PGAUDIT_ARCHIVE REPORT.json}
architecture=arm64
pg_version=18.6
pgaudit_version=18.0
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
for archive in "$core_archive" "$extension_archive"; do
  test -s "$archive" && test -s "$archive.sha256"
  (cd "$(dirname "$archive")" && shasum -a 256 -c "$(basename "$archive").sha256")
done
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "Diagnostics require native macOS $architecture" >&2
  exit 1
fi

work=$(mktemp -d /tmp/pgaudit-macos-diagnostics.XXXXXX)
pg_ctl=
data_dir=
cleanup() {
  if [[ -n $pg_ctl && -n $data_dir ]]; then
    "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/missing" "$work/valid" "$work/missing-socket" "$work/valid-socket" "$(dirname "$report")"
assemble() {
  local destination=$1
  tar -xzf "$core_archive" -C "$destination"
  tar -xzf "$extension_archive" -C "$destination"
  python3 - "$destination/postgresql" "$destination/pgaudit" <<'PY'
from pathlib import Path
import sys

core, extension = map(Path, sys.argv[1:])
for source in extension.rglob("*"):
    destination = core / source.relative_to(extension)
    if destination.exists() or destination.is_symlink():
        if source.is_dir() and destination.is_dir() and not source.is_symlink() and not destination.is_symlink():
            continue
        raise SystemExit(f"pgAudit payload collision: {source.relative_to(extension)}")
PY
  ditto "$destination/pgaudit" "$destination/postgresql"
}
assemble "$work/missing"
root="$work/missing/postgresql"
module="$root/lib/pgaudit.dylib"
test -s "$module"
mv "$module" "$work/pgaudit.dylib.hidden"
data_dir="$work/missing-data"
log="$work/missing-server.log"
"$root/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >/dev/null
pg_ctl="$root/bin/pg_ctl"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
set +e
missing_output=$("$pg_ctl" -D "$data_dir" -l "$log" -o \
  "-k $work/missing-socket -p 55437 -h '' -c shared_preload_libraries=pgaudit" -w start 2>&1)
missing_status=$?
set -e
if [[ $missing_status -eq 0 ]] || ! grep -Eqi 'could not access file|could not load library|pgaudit' "$log"; then
  echo "Missing pgAudit module did not produce the expected startup diagnostic" >&2
  cat "$log" >&2
  exit 1
fi
"$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
pg_ctl=
data_dir=

assemble "$work/valid"
root="$work/valid/postgresql"
data_dir="$work/valid-data"
log="$work/valid-server.log"
"$root/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >/dev/null
pg_ctl="$root/bin/pg_ctl"
"$pg_ctl" -D "$data_dir" -l "$log" -o \
  "-k $work/valid-socket -p 55438 -h '' -c shared_preload_libraries=pgaudit" -w start
set +e
client_output=$("$root/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/valid-socket" \
  -p 55438 -d postgres -c 'SELECT 1 / 0;' 2>&1)
client_status=$?
set -e
if [[ $client_status -eq 0 ]] || ! grep -Fq 'ERROR:  division by zero' "$log"; then
  echo "PostgreSQL failure did not produce the expected server log entry" >&2
  cat "$log" >&2
  exit 1
fi
"$pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=
pg_ctl=

PG_REPORT="$report" PG_CORE_ARCHIVE="$core_archive" PG_EXTENSION_ARCHIVE="$extension_archive" \
PG_PG_VERSION="$pg_version" PG_PGAUDIT_VERSION="$pgaudit_version" PG_ARCH="$architecture" \
PG_MISSING_STATUS="$missing_status" PG_MISSING_OUTPUT="$missing_output" \
PG_MISSING_LOG="$work/missing-server.log" PG_CLIENT_STATUS="$client_status" \
PG_CLIENT_OUTPUT="$client_output" PG_SERVER_LOG="$work/valid-server.log" python3 - <<'PY'
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

report = {
    "schema_version": 1,
    "platform": "macos",
    "architecture": os.environ["PG_ARCH"],
    "os_version": subprocess.run(["sw_vers", "-productVersion"], check=True,
                                  text=True, capture_output=True).stdout.strip(),
    "kernel": platform.release(),
    "postgresql_version": os.environ["PG_PG_VERSION"],
    "pgaudit_version": os.environ["PG_PGAUDIT_VERSION"],
    "archives": {
        Path(os.environ["PG_CORE_ARCHIVE"]).name: sha256(os.environ["PG_CORE_ARCHIVE"]),
        Path(os.environ["PG_EXTENSION_ARCHIVE"]).name: sha256(os.environ["PG_EXTENSION_ARCHIVE"]),
    },
    "extension_load_failure": {
        "kind": "missing-preload-module",
        "exit_code": int(os.environ["PG_MISSING_STATUS"]),
        "command_output": os.environ["PG_MISSING_OUTPUT"],
        "server_log": Path(os.environ["PG_MISSING_LOG"]).read_text(errors="replace"),
    },
    "postgresql_failure": {
        "kind": "server-error",
        "command": "psql -X -v ON_ERROR_STOP=1 -c 'SELECT 1 / 0;'",
        "exit_code": int(os.environ["PG_CLIENT_STATUS"]),
        "client_output": os.environ["PG_CLIENT_OUTPUT"],
        "server_log": Path(os.environ["PG_SERVER_LOG"]).read_text(errors="replace"),
    },
}
if not report["extension_load_failure"]["server_log"] or not report["postgresql_failure"]["server_log"]:
    raise SystemExit("diagnostic evidence is incomplete")
Path(os.environ["PG_REPORT"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
PY
echo "pgAudit macOS failure diagnostics written to $report"
