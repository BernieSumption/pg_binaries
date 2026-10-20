#!/usr/bin/env bash
set -euo pipefail

core_archive=${1:?usage: macos-archive-suite.sh CORE_ARCHIVE PGAUDIT_ARCHIVE PG_VERSION ARCHITECTURE}
extension_archive=${2:?usage: macos-archive-suite.sh CORE_ARCHIVE PGAUDIT_ARCHIVE PG_VERSION ARCHITECTURE}
pg_version=${3:?PostgreSQL version is required}
architecture=${4:?architecture is required}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "Archive suite requires native macOS $architecture" >&2
  exit 1
fi

for archive in "$core_archive" "$extension_archive"; do
  test -s "$archive" && test -s "$archive.sha256"
  (cd "$(dirname "$archive")" && shasum -a 256 -c "$(basename "$archive").sha256")
done

work=$(mktemp -d /tmp/pgaudit-macos-archive-suite.XXXXXX)
pg_ctl=
data_dir=
cleanup() {
  if [[ -n $pg_ctl && -n $data_dir ]]; then
    "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/assembled" "$work/relocated" "$work/socket"
tar -xzf "$core_archive" -C "$work/assembled"
tar -xzf "$extension_archive" -C "$work/assembled"
python3 - "$work/assembled/postgresql" "$work/assembled/pgaudit" <<'PY'
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
ditto "$work/assembled/pgaudit" "$work/assembled/postgresql"
mv "$work/assembled/postgresql" "$work/relocated/postgresql"
root="$work/relocated/postgresql"
test "$("$root/bin/pg_config" --version)" = "PostgreSQL $pg_version"

export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
data_dir="$work/data"
pg_ctl="$root/bin/pg_ctl"
"$root/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >/dev/null
"$pg_ctl" -D "$data_dir" -l "$work/server.log" -o \
  "-k $work/socket -p 55439 -h '' -c shared_preload_libraries=pgaudit" -w start
"$root/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55439 \
  -d postgres -f "$repo/scripts/pgaudit/probe.sql" | tee "$work/probe-output.txt"
grep -Fq 'audit payload' "$work/probe-output.txt"
"$pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=
pg_ctl=
echo "PASS: downloaded pgAudit archive suite on fresh macOS $architecture runner"
