#!/usr/bin/env bash
set -euo pipefail

archives=$(cd "${1:?archive directory required}" && pwd)
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
pg_name=postgresql-18.6-macos-x86_64.tar.gz
vector_name=pgvector-0.8.7-postgresql-18.6-macos-x86_64.tar.gz
work=$(mktemp -d /tmp/pgv.XXXXXX)
data_dir=
pg_ctl=
cleanup() {
  if [[ -n $data_dir && -n $pg_ctl ]]; then
    "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT

cd "$archives"
shasum -a 256 -c "$pg_name.sha256" "$vector_name.sha256"
mkdir -p "$work/first" "$work/moved" "$work/socket"
tar -xzf "$archives/$pg_name" -C "$work/first"
tar -xzf "$archives/$vector_name" -C "$work/first"

python3 - "$work/first/postgresql/manifest.json" "$work/first/pgvector/manifest.json" <<'PY'
import json, sys
pg, vector = [json.load(open(path)) for path in sys.argv[1:]]
expected = {"schema_version": 1, "postgresql_version": "18.6", "platform": "macos", "architecture": "x86_64"}
for artifact in (pg, vector):
    for key, value in expected.items():
        if artifact.get(key) != value:
            raise SystemExit(f"artifact mismatch: {key}: {artifact.get(key)!r} != {value!r}")
if pg.get("component") != "postgresql" or pg.get("version") != "18.6":
    raise SystemExit("PostgreSQL manifest mismatch")
if vector.get("component") != "pgvector" or vector.get("version") != "0.8.7":
    raise SystemExit("pgvector manifest mismatch")
PY
test -s "$work/first/postgresql/LICENSES/PostgreSQL.txt"
test -s "$work/first/pgvector/LICENSES/pgvector.txt"

start_server() {
  local pg_root=$1
  local run_name=$2
  pg_ctl="$pg_root/bin/pg_ctl"
  data_dir="$work/$run_name-data"
  "$pg_root/bin/initdb" -D "$data_dir" --no-instructions >/dev/null
  "$pg_ctl" -D "$data_dir" -o "-k $work/socket -p 54329 -c listen_addresses=''" -l "$work/$run_name.log" -w start
  "$pg_root/bin/psql" -h "$work/socket" -p 54329 -d postgres -XAt -c 'SHOW server_version' | grep -Fx '18.6'
}
stop_server() {
  "$pg_ctl" -D "$data_dir" -m fast -w stop
  data_dir=
  pg_ctl=
}

export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
start_server "$work/first/postgresql" first
stop_server
mv "$work/first/postgresql" "$work/moved/postgresql"
pg="$work/moved/postgresql"
start_server "$pg" moved
psql=("$pg/bin/psql" -h "$work/socket" -p 54329 -d postgres -X -v ON_ERROR_STOP=1)

"${psql[@]}" -f "$repo/tests/schema.sql"
"${psql[@]}" -c "CREATE COLLATION pilot_icu (provider = icu, locale = 'und-u-ks-level2', deterministic = false)"
"${psql[@]}" -c "SELECT name FROM (VALUES ('a'), ('A')) AS names(name) ORDER BY name COLLATE pilot_icu"
locale_name=$(locale -a | awk '/UTF-8|utf8/ && !found {print; found=1}')
if [[ -z $locale_name ]]; then
  echo 'No UTF-8 libc locale available on macOS verifier' >&2
  exit 1
fi
printf "CREATE COLLATION pilot_libc (provider = libc, locale = '%s');\n" "$locale_name" | "${psql[@]}"
"${psql[@]}" -c "SELECT name FROM (VALUES ('a'), ('b')) AS names(name) ORDER BY name COLLATE pilot_libc"
"${psql[@]}" -c "CREATE TABLE pilot_compressed (payload text COMPRESSION lz4)"
"${psql[@]}" -c "INSERT INTO pilot_compressed SELECT repeat('compression-test', 10000)"
"${psql[@]}" -At -c "SELECT pg_column_compression(payload) FROM pilot_compressed" | grep -Fx lz4
"${psql[@]}" -c "ALTER SYSTEM SET wal_compression = 'zstd'"
"${psql[@]}" -c "SELECT pg_reload_conf()"
"${psql[@]}" -At -c "SHOW wal_compression" | grep -Fx zstd

ditto "$work/first/pgvector/lib" "$pg/lib"
ditto "$work/first/pgvector/share" "$pg/share"
"${psql[@]}" -c 'CREATE EXTENSION vector'
"${psql[@]}" -At -c "SELECT extversion FROM pg_extension WHERE extname = 'vector'" | grep -Fx '0.8.7'
"${psql[@]}" -At -c "SELECT '[1,2,3]'::vector <-> '[2,3,4]'::vector" | grep -Fx '1.7320508075688772'
"${psql[@]}" -c "CREATE TABLE pilot_vectors (id int PRIMARY KEY, embedding vector(3))"
"${psql[@]}" -c "INSERT INTO pilot_vectors VALUES (1, '[1,2,3]'), (2, '[2,3,4]')"
"${psql[@]}" -c "CREATE INDEX ON pilot_vectors USING hnsw (embedding vector_l2_ops)"
"${psql[@]}" -At -c "SELECT id FROM pilot_vectors ORDER BY embedding <-> '[1,2,3]' LIMIT 1" | grep -Fx 1
stop_server

python3 - "$pg" <<'PY'
import pathlib, subprocess, sys
for binary in pathlib.Path(sys.argv[1]).rglob('*'):
    if not binary.is_file() or binary.is_symlink() or binary.suffix == '.a':
        continue
    result = subprocess.run(['otool', '-L', str(binary)], capture_output=True, text=True)
    if result.returncode:
        continue
    for line in result.stdout.splitlines()[1:]:
        dep = line.strip().split(' ', 1)[0]
        if dep.startswith('/') and not dep.startswith(('/usr/lib/', '/System/Library/')):
            raise SystemExit(f'Non-system absolute Mach-O dependency: {binary}: {dep}')
PY
echo "macOS packaged archive verification passed on $(sw_vers -productVersion), $(uname -m), libc locale $locale_name"
