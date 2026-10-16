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
mkdir -p "$work/first" "$work/extension" "$work/moved" "$work/socket"
tar -xzf "$archives/$pg_name" -C "$work/first"
tar -xzf "$archives/$vector_name" -C "$work/extension"

python3 - "$work/first/postgresql" "$work/extension" <<'PY'
import json, pathlib, sys
core, extension = map(pathlib.Path, sys.argv[1:])
pg = json.loads((core / 'manifest.json').read_text())
vector = json.loads((extension / 'metadata.json').read_text())
expected = {"schema_version": 1, "postgresql_version": "18.6", "platform": "macos", "architecture": "x86_64"}
for key, value in expected.items():
    if pg.get(key) != value:
        raise SystemExit(f"PostgreSQL manifest mismatch: {key}: {pg.get(key)!r} != {value!r}")
if pg.get("component") != "postgresql" or pg.get("version") != "18.6":
    raise SystemExit("PostgreSQL manifest mismatch")
controls = {path.stem for path in (core / 'share/extension').glob('*.control')}
if not controls or pg.get('included_extensions') != sorted(controls) or 'vector' in controls:
    raise SystemExit('built-in extension inventory mismatch')
if vector != {'project': 'pgvector', 'version': '0.8.7', 'sql_names': ['vector'],
              'requires': [], 'configuration_prerequisites': [], 'runtime_prerequisites': []}:
    raise SystemExit('pgvector metadata mismatch')
for source in (extension / 'pgvector').rglob('*'):
    destination = core / source.relative_to(extension / 'pgvector')
    if destination.exists() or destination.is_symlink():
        if source.is_dir() and not source.is_symlink() and destination.is_dir() and not destination.is_symlink():
            continue
        raise SystemExit(f'extension payload collision: {source.relative_to(extension / "pgvector")}')
PY
test -s "$work/first/postgresql/LICENSES/PostgreSQL.txt"
test -s "$work/extension/pgvector/LICENSES/pgvector.txt"
ditto "$work/extension/pgvector" "$work/first/postgresql"
test -s "$work/first/postgresql/LICENSES/pgvector.txt"

start_server() {
  local pg_root=$1
  local run_name=$2
  pg_ctl="$pg_root/bin/pg_ctl"
  data_dir="$work/$run_name-data"
  "$pg_root/bin/initdb" -D "$data_dir" --encoding=UTF8 --no-instructions >/dev/null
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
first_psql=("$work/first/postgresql/bin/psql" -h "$work/socket" -p 54329 -d postgres -X -v ON_ERROR_STOP=1)
"${first_psql[@]}" -f "$repo/tests/schema.sql"
"${first_psql[@]}" -c 'CREATE EXTENSION vector'
"${first_psql[@]}" -c 'CREATE TABLE first_vectors (embedding vector(3))'
"${first_psql[@]}" -c "INSERT INTO first_vectors VALUES ('[1,0,0]')"
"${first_psql[@]}" -At -c "SELECT embedding <-> '[1,0,0]'::vector FROM first_vectors" | grep -Fx 0
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

"${psql[@]}" -c 'CREATE EXTENSION vector'
"${psql[@]}" -At -c "SELECT extversion FROM pg_extension WHERE extname = 'vector'" | grep -Fx '0.8.7'
"${psql[@]}" -At -c "SELECT '[1,2,3]'::vector <-> '[2,3,4]'::vector" | grep -Fx '1.7320508075688772'
"${psql[@]}" -c "CREATE TABLE pilot_vectors (id int PRIMARY KEY, embedding vector(3))"
"${psql[@]}" -c "INSERT INTO pilot_vectors VALUES (1, '[1,2,3]'), (2, '[2,3,4]')"
"${psql[@]}" -c "CREATE INDEX ON pilot_vectors USING hnsw (embedding vector_l2_ops)"
"${psql[@]}" -At -c "SELECT id FROM pilot_vectors ORDER BY embedding <-> '[1,2,3]' LIMIT 1" | grep -Fx 1
"$pg/bin/pg_dump" -h "$work/socket" -p 54329 -Fc -Z zstd:1 -f "$work/pilot.dump" postgres
"${psql[@]}" -c 'CREATE DATABASE restored'
"$pg/bin/pg_restore" --exit-on-error -h "$work/socket" -p 54329 -d restored "$work/pilot.dump"
restored=("$pg/bin/psql" -h "$work/socket" -p 54329 -d restored -X -v ON_ERROR_STOP=1)
"${restored[@]}" -At -c 'SELECT pilot.active_item_count(1)' | grep -Fx 1
"${restored[@]}" -At -c "SELECT id FROM pilot_vectors ORDER BY embedding <-> '[1,2,3]' LIMIT 1" | grep -Fx 1
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
