#!/usr/bin/env bash
set -euo pipefail

core_only=false
if [[ ${1:-} == --core-only ]]; then
  core_only=true
  shift
fi
if [[ ${1:-} == --help ]]; then
  echo "Usage: verify.sh [--core-only] ARCHIVE_DIRECTORY [ARCHITECTURE] [POSTGRESQL_VERSION]"
  exit 0
fi
archives=$(cd "${1:?archive directory required}" && pwd)
architecture=${2:-$(uname -m)}
pg_version=${3:-18.6}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported macOS architecture: $architecture" >&2; exit 1 ;; esac
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "Verification requires native macOS $architecture" >&2
  exit 1
fi
pg_name="postgresql-${pg_version}-macos-${architecture}.tar.gz"
vector_name="pgvector-0.8.7-postgresql-${pg_version}-macos-${architecture}.tar.gz"
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
if $core_only; then
  shasum -a 256 -c "$pg_name.sha256"
else
  shasum -a 256 -c "$pg_name.sha256" "$vector_name.sha256"
fi
python3 "$repo/tools/check_macos_license_inventory.py" "$archives/$pg_name"
if ! $core_only; then python3 "$repo/tools/check_macos_license_inventory.py" "$archives/$vector_name"; fi
mkdir -p "$work/first" "$work/extension" "$work/moved" "$work/socket"
tar -xzf "$archives/$pg_name" -C "$work/first"
if ! $core_only; then tar -xzf "$archives/$vector_name" -C "$work/extension"; fi
source_args=(--platform macos --postgresql-version "$pg_version" --core-manifest "$work/first/postgresql/manifest.json")
if ! $core_only; then source_args+=(--vector-metadata "$work/extension/metadata.json"); fi
python3 "$repo/tools/check_source_identity.py" "${source_args[@]}"

python3 - "$work/first/postgresql" "$architecture" "$pg_version" "$core_only" "$work/extension" <<'PY'
import json, pathlib, re, sys
core = pathlib.Path(sys.argv[1])
core_only = sys.argv[4] == 'true'
pg = json.loads((core / 'manifest.json').read_text())
expected = {"schema_version": 1, "postgresql_version": sys.argv[3], "platform": "macos", "architecture": sys.argv[2]}
for key, value in expected.items():
    if pg.get(key) != value:
        raise SystemExit(f"PostgreSQL manifest mismatch: {key}: {pg.get(key)!r} != {value!r}")
if pg.get("component") != "postgresql" or pg.get("version") != sys.argv[3]:
    raise SystemExit("PostgreSQL manifest mismatch")
provenance_fields = ('build_id', 'source_revision', 'build_configuration', 'platform', 'architecture')
provenance = {field: pg.get(field) for field in provenance_fields}
if not isinstance(provenance['build_id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', provenance['build_id']):
    raise SystemExit('PostgreSQL build identifier is missing or invalid')
if not isinstance(provenance['source_revision'], str) or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', provenance['source_revision']):
    raise SystemExit('PostgreSQL source revision is missing or invalid')
if not isinstance(provenance['build_configuration'], str) or not provenance['build_configuration']:
    raise SystemExit('PostgreSQL build configuration is missing')
controls = {path.stem for path in (core / 'share/extension').glob('*.control')}
if not controls or pg.get('included_extensions') != sorted(controls) or 'vector' in controls or 'uuid-ossp' not in controls:
    raise SystemExit('built-in extension inventory mismatch')
if not core_only:
    extension = pathlib.Path(sys.argv[5])
    vector = json.loads((extension / 'metadata.json').read_text())
    expected_vector = {'project': 'pgvector', 'version': '0.8.7', 'sql_names': ['vector'],
                       'requires': [], 'configuration_prerequisites': [], 'runtime_prerequisites': []}
    if any(vector.get(key) != value for key, value in expected_vector.items()):
        raise SystemExit('pgvector metadata mismatch')
    if any(vector.get(field) != value for field, value in provenance.items()):
        raise SystemExit('pgvector build provenance differs from PostgreSQL')
    licence_inventory = extension / 'pgvector/LICENSES/pgvector-inventory.json'
    inventory = json.loads(licence_inventory.read_text())
    if inventory.get('schema_version') != 1 or not inventory.get('components'):
        raise SystemExit('pgvector licence inventory missing components')
    for source in (extension / 'pgvector').rglob('*'):
        destination = core / source.relative_to(extension / 'pgvector')
        if destination.exists() or destination.is_symlink():
            if source.is_dir() and not source.is_symlink() and destination.is_dir() and not destination.is_symlink():
                continue
            raise SystemExit(f'extension payload collision: {source.relative_to(extension / "pgvector")}')
PY
test -s "$work/first/postgresql/LICENSES/PostgreSQL.txt"
if ! $core_only; then
  test -s "$work/extension/pgvector/LICENSES/pgvector.txt"
  ditto "$work/extension/pgvector" "$work/first/postgresql"
  test -s "$work/first/postgresql/LICENSES/pgvector.txt"
fi

start_server() {
  local pg_root=$1
  local run_name=$2
  pg_ctl="$pg_root/bin/pg_ctl"
  data_dir="$work/$run_name-data"
  "$pg_root/bin/initdb" -D "$data_dir" --encoding=UTF8 --no-instructions >/dev/null
  local server_options="-k $work/socket -p 54329 -c listen_addresses=''"
  if [[ $run_name == moved ]]; then
    mkdir -p "$work/tls"
    openssl req -x509 -newkey rsa:2048 -sha256 -days 1 -nodes -subj '/CN=pilot-ca' -keyout "$work/tls/ca.key" -out "$work/tls/ca.crt" >/dev/null 2>&1
    for peer in server client; do
      if [[ $peer == server ]]; then cn=localhost; else cn=$(id -un); fi
      openssl req -newkey rsa:2048 -sha256 -nodes -subj "/CN=$cn" -keyout "$work/tls/$peer.key" -out "$work/tls/$peer.csr" >/dev/null 2>&1
      openssl x509 -req -in "$work/tls/$peer.csr" -CA "$work/tls/ca.crt" -CAkey "$work/tls/ca.key" -CAcreateserial -days 1 -sha256 -out "$work/tls/$peer.crt" >/dev/null 2>&1
    done
    chmod 600 "$work/tls"/*.key
    printf 'local all all trust\nhostssl all all 127.0.0.1/32 cert\n' > "$data_dir/pg_hba.conf"
    server_options="-k $work/socket -p 54329 -h 127.0.0.1 -c shared_preload_libraries=pg_stat_statements -c wal_level=logical -c ssl=on -c ssl_cert_file=$work/tls/server.crt -c ssl_key_file=$work/tls/server.key -c ssl_ca_file=$work/tls/ca.crt"
  fi
  "$pg_ctl" -D "$data_dir" -o "$server_options" -l "$work/$run_name.log" -w start
  "$pg_root/bin/psql" -h "$work/socket" -p 54329 -d postgres -XAt -c 'SHOW server_version' | grep -Fx "$pg_version"
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
"${psql[@]}" -f "$repo/tests/builtins/basic.sql"
"${psql[@]}" -v loopback_conninfo="host=$work/socket port=54329 dbname=postgres" -v loopback_host="$work/socket" -v loopback_port=54329 -f "$repo/tests/builtins/loopback.sql"
"${psql[@]}" -v fixture_path="$repo/tests/builtins/file_fdw.csv" -f "$repo/tests/builtins/fixture.sql"
"${psql[@]}" -f "$repo/tests/builtins/preloaded.sql"
"${psql[@]}" -f "$repo/tests/builtins/wal.sql"
tcn_output=$("${psql[@]}" -f "$repo/tests/builtins/tcn.sql")
printf '%s\n' "$tcn_output"
grep -F "Asynchronous notification \"tcn\" with payload \"\"builtin_tcn\",I,\"id\"='91'\"" <<< "$tcn_output"
PGSSLMODE=verify-ca PGSSLROOTCERT="$work/tls/ca.crt" PGSSLCERT="$work/tls/client.crt" PGSSLKEY="$work/tls/client.key" \
  "$pg/bin/psql" -h 127.0.0.1 -p 54329 -d postgres -X -v ON_ERROR_STOP=1 -f "$repo/tests/builtins/ssl.sql"
if [[ $pg_version == 18.* ]]; then
  "${psql[@]}" -f "$repo/tests/builtins/logical.sql"
fi
if [[ $pg_version == 15.* || $pg_version == 16.* ]]; then
  "${psql[@]}" -f "$repo/tests/builtins/legacy.sql"
fi
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

if ! $core_only; then "${psql[@]}" -f "$repo/tests/extensions/pgvector.sql"; fi
"${psql[@]}" -f "$repo/tests/builtins/coverage.sql"
dump_compression=(-Z zstd:1)
if [[ $pg_version == 15.* ]]; then dump_compression=(-Z 1); fi
"$pg/bin/pg_dump" -h "$work/socket" -p 54329 -Fc "${dump_compression[@]}" -f "$work/pilot.dump" postgres
"${psql[@]}" -c 'CREATE DATABASE restored'
"$pg/bin/pg_restore" --exit-on-error -h "$work/socket" -p 54329 -d restored "$work/pilot.dump"
restored=("$pg/bin/psql" -h "$work/socket" -p 54329 -d restored -X -v ON_ERROR_STOP=1)
"${restored[@]}" -At -c 'SELECT pilot.active_item_count(1)' | grep -Fx 1
if ! $core_only; then
  "${restored[@]}" -At -c "SELECT id FROM pilot_vectors ORDER BY embedding <-> '[1,0,0]'::vector LIMIT 1" | grep -Fx 1
fi
"${psql[@]}" -c 'CREATE DATABASE surgery_check'
surgery=("$pg/bin/psql" -h "$work/socket" -p 54329 -d surgery_check -X -v ON_ERROR_STOP=1)
"${surgery[@]}" -f "$repo/tests/builtins/surgery.sql"
stop_server

static_report=${MACOS_STATIC_ANALYSIS_REPORT:-$work/macos-static-analysis.json}
static_args=(--archive "$archives/$pg_name" --report "$static_report")
if ! $core_only; then static_args+=(--archive "$archives/$vector_name"); fi
python3 "$repo/scripts/macos/static_analysis.py" "$pg" "$architecture" "${static_args[@]}"
echo "macOS packaged archive verification passed on $(sw_vers -productVersion), $(uname -m), libc locale $locale_name"
