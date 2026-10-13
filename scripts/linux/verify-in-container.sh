#!/usr/bin/env bash
set -euo pipefail
pg=postgresql-18.6-linux-x86_64.tar.gz
vector=pgvector-0.8.7-postgresql-18.6-linux-x86_64.tar.gz
cd /out
sha256sum -c "$pg.sha256" "$vector.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/vector
tar -xzf "$pg" -C /tmp/first
tar -xzf "$vector" -C /tmp/vector
python3 - <<'PY'
import json
for path, component, version in [
    ('/tmp/first/postgresql/manifest.json', 'postgresql', '18.6'),
    ('/tmp/vector/pgvector/manifest.json', 'pgvector', '0.8.7'),
]:
    with open(path) as f:
        m = json.load(f)
    assert (m['schema_version'], m['component'], m['version'],
            m['postgresql_version'], m['platform'], m['architecture']) == (
                1, component, version, '18.6', 'linux', 'x86_64'), m
PY
test -s /tmp/first/postgresql/LICENSES/PostgreSQL.txt
test -s /tmp/vector/pgvector/LICENSES/pgvector.txt
test "$(/tmp/first/postgresql/bin/postgres --version)" = 'postgres (PostgreSQL) 18.6'
mv /tmp/first/postgresql /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
cp /tmp/vector/pgvector/lib/* "$pgroot/lib/"
cp /tmp/vector/pgvector/share/extension/* "$pgroot/share/extension/"
useradd -m postgres
mkdir -p /tmp/pgdata /tmp/pgsocket
chown postgres:postgres /tmp/pgdata /tmp/pgsocket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/pgdata --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/pgdata -o '-k /tmp/pgsocket -p 55431 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/pgdata -m immediate stop >/dev/null 2>&1 || true' EXIT
psql=(runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/pgsocket -p 55431 -d postgres)
"${psql[@]}" -Atqc 'SELECT version()' | grep -F 'PostgreSQL 18.6'
"${psql[@]}" -f /tests/schema.sql
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
runuser -u postgres -- "$pgroot/bin/pg_dump" -h /tmp/pgsocket -p 55431 -Fc -Z zstd:1 -f /tmp/probe.dump postgres
runuser -u postgres -- "$pgroot/bin/pg_restore" -l /tmp/probe.dump >/dev/null
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/pgdata -m fast -w stop
trap - EXIT
echo 'PASS: moved PostgreSQL 18.6 archive and pgvector 0.8.7 archive on Ubuntu 24.04'
