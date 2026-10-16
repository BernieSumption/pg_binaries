#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
case "$architecture:$(uname -m)" in
  x86_64:x86_64|arm64:aarch64) ;;
  *) echo "Verifier container architecture does not match $architecture: $(uname -m)" >&2; exit 2 ;;
esac
if [[ ! $pg_version =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Linux pilot currently supports PostgreSQL 15 through 18 minors only: $pg_version" >&2
  exit 2
fi
pg="postgresql-${pg_version}-linux-${architecture}.tar.gz"
vector="pgvector-0.8.7-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /out
sha256sum -c "$pg.sha256" "$vector.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/vector
tar -xzf "$pg" -C /tmp/first
tar -xzf "$vector" -C /tmp/vector
python3 - "$pg_version" "$architecture" <<'PY'
import json
from pathlib import Path
import sys
version = sys.argv[1]
architecture = sys.argv[2]
with open('/tmp/first/postgresql/manifest.json') as f:
    m = json.load(f)
assert (m['schema_version'], m['component'], m['version'],
        m['postgresql_version'], m['platform'], m['architecture']) == (
            1, 'postgresql', version, version, 'linux', architecture), m
controls = {path.stem for path in Path('/tmp/first/postgresql/share/extension').glob('*.control')}
assert controls and m['included_extensions'] == sorted(controls), m
assert 'vector' not in controls, controls

with open('/tmp/vector/metadata.json') as f:
    m = json.load(f)
assert m == {
    'project': 'pgvector',
    'version': '0.8.7',
    'sql_names': ['vector'],
    'requires': [],
    'configuration_prerequisites': [],
    'runtime_prerequisites': [],
}, m
PY
test -s /tmp/first/postgresql/LICENSES/PostgreSQL.txt
test -s /tmp/vector/pgvector/LICENSES/pgvector.txt
for package in libicu70 libssl3 liblz4-1 libzstd1 libxml2 libxslt1.1; do
  test -s "/tmp/first/postgresql/LICENSES/$package.copyright"
done
pgroot=/tmp/first/postgresql
extroot=/tmp/vector/pgvector
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then
      continue
    fi
    echo "Extension payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
cp -a "$extroot/." "$pgroot/"
test -s "$pgroot/LICENSES/pgvector.txt"
python3 /usr/local/bin/check-elf-dependencies "$pgroot"
test "$(/tmp/first/postgresql/bin/postgres --version)" = "postgres (PostgreSQL) $pg_version"
useradd -m postgres
mkdir -p /tmp/first-data /tmp/first-socket
chown postgres:postgres /tmp/first-data /tmp/first-socket
runuser -u postgres -- /tmp/first/postgresql/bin/initdb -D /tmp/first-data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- /tmp/first/postgresql/bin/pg_ctl -D /tmp/first-data -o '-k /tmp/first-socket -p 55430 -h ""' -w start
trap 'runuser -u postgres -- /tmp/first/postgresql/bin/pg_ctl -D /tmp/first-data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- /tmp/first/postgresql/bin/psql -XAt -h /tmp/first-socket -p 55430 -d postgres -c 'SHOW server_version' | grep -Fx "$pg_version"
runuser -u postgres -- /tmp/first/postgresql/bin/psql -X -v ON_ERROR_STOP=1 -h /tmp/first-socket -p 55430 -d postgres <<'SQL'
CREATE EXTENSION vector;
CREATE TABLE relocation_probe (embedding vector(3));
INSERT INTO relocation_probe VALUES ('[1,0,0]');
DO $$ BEGIN IF (SELECT embedding <-> '[1,0,0]'::vector FROM relocation_probe) <> 0 THEN
  RAISE EXCEPTION 'pgvector smoke test failed'; END IF; END $$;
SQL
runuser -u postgres -- /tmp/first/postgresql/bin/pg_ctl -D /tmp/first-data -m fast -w stop
trap - EXIT
mv /tmp/first/postgresql /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
mkdir -p /tmp/pgdata /tmp/pgsocket
chown postgres:postgres /tmp/pgdata /tmp/pgsocket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/pgdata --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/pgdata -o '-k /tmp/pgsocket -p 55431 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/pgdata -m immediate stop >/dev/null 2>&1 || true' EXIT
psql=(runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/pgsocket -p 55431 -d postgres)
"${psql[@]}" -Atqc 'SELECT version()' | grep -F "PostgreSQL $pg_version"
"${psql[@]}" -f /tests/schema.sql
"${psql[@]}" -f /tests/builtins/basic.sql
"${psql[@]}" -f /tests/builtins/loopback.sql
"${psql[@]}" <<'SQL'
CREATE COLLATION pilot_icu (provider = icu, locale = 'en-US-u-kn-true', deterministic = false);
CREATE COLLATION pilot_libc (provider = libc, locale = 'C');
SELECT 'a' < 'b' COLLATE pilot_icu;
SELECT 'a' < 'b' COLLATE pilot_libc;
CREATE TABLE compression_probe (id integer, lz text COMPRESSION lz4, native text COMPRESSION pglz);
INSERT INTO compression_probe VALUES (1, repeat('compress me', 1000), repeat('compress me', 1000));
DO $$ BEGIN IF (SELECT pg_column_compression(lz) FROM compression_probe) <> 'lz4' THEN
  RAISE EXCEPTION 'LZ4 compression not used'; END IF; END $$;
SET wal_compression = zstd;
SHOW wal_compression;
CREATE EXTENSION vector;
DO $$ BEGIN IF (SELECT extversion FROM pg_extension WHERE extname='vector') <> '0.8.7' THEN
  RAISE EXCEPTION 'wrong pgvector version'; END IF; END $$;
CREATE TABLE embedding (id integer PRIMARY KEY, embedding vector(3));
INSERT INTO embedding VALUES (1, '[1,0,0]'), (2, '[0,1,0]'), (3, '[0,0,1]');
CREATE INDEX embedding_hnsw ON embedding USING hnsw (embedding vector_l2_ops);
SELECT id, embedding <-> '[1,0,0]'::vector AS distance FROM embedding ORDER BY distance LIMIT 2;
SQL
if [[ $pg_version == 15.* ]]; then
  dump_compression=(-Z 1)
else
  dump_compression=(-Z zstd:1)
fi
runuser -u postgres -- "$pgroot/bin/pg_dump" -h /tmp/pgsocket -p 55431 -Fc "${dump_compression[@]}" -f /tmp/probe.dump postgres
"${psql[@]}" -c 'CREATE DATABASE restored'
runuser -u postgres -- "$pgroot/bin/pg_restore" --exit-on-error -h /tmp/pgsocket -p 55431 -d restored /tmp/probe.dump
restored=(runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/pgsocket -p 55431 -d restored)
"${restored[@]}" <<'SQL'
DO $$ BEGIN
  IF pilot.active_item_count(1) <> 1 THEN RAISE EXCEPTION 'restored function or data missing'; END IF;
  IF (SELECT count(*) FROM pilot.events_2026) <> 1 THEN RAISE EXCEPTION 'restored partition data missing'; END IF;
  IF (SELECT extversion FROM pg_extension WHERE extname = 'vector') <> '0.8.7' THEN
    RAISE EXCEPTION 'restored pgvector missing'; END IF;
  IF (SELECT embedding <-> '[1,0,0]'::vector FROM embedding WHERE id = 1) <> 0 THEN
    RAISE EXCEPTION 'restored vector data missing'; END IF;
END $$;
SQL
"${psql[@]}" -c 'CREATE DATABASE surgery_check'
surgery=(runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/pgsocket -p 55431 -d surgery_check)
"${surgery[@]}" -f /tests/builtins/surgery.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/pgdata -m fast -w stop
trap - EXIT
. /etc/os-release
echo "PASS: moved PostgreSQL $pg_version archive and pgvector 0.8.7 archive on $PRETTY_NAME"
