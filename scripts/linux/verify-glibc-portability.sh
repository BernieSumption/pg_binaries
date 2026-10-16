#!/bin/sh
set -eu

archives=${1:?usage: verify-glibc-portability.sh ARCHIVES PG_VERSION ARCHITECTURE}
version=${2:?}
architecture=${3:?}
pg_archive="postgresql-$version-linux-$architecture.tar.gz"
vector_archive="pgvector-0.8.7-postgresql-$version-linux-$architecture.tar.gz"
cd "$archives"
sha256sum -c "$pg_archive.sha256" "$vector_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/vector /tmp/data /tmp/socket
tar -xzf "$pg_archive" -C /tmp/first
tar -xzf "$vector_archive" -C /tmp/vector
cp -a /tmp/vector/pgvector/. /tmp/first/postgresql/
mv /tmp/first/postgresql /tmp/moved/postgresql
root=/tmp/moved/postgresql
test ! -e /tmp/first/postgresql
test "$("$root/bin/postgres" --version)" = "postgres (PostgreSQL) $version"
chown nobody /tmp/data /tmp/socket
su -s /bin/sh nobody -c "$root/bin/initdb -D /tmp/data --encoding=UTF8 --locale=C --no-instructions"
su -s /bin/sh nobody -c "$root/bin/pg_ctl -D /tmp/data -o '-k /tmp/socket -p 55439 -h 127.0.0.1' -w start"
stop_server() {
  su -s /bin/sh nobody -c "$root/bin/pg_ctl -D /tmp/data -m immediate stop" >/dev/null 2>&1 || true
}
trap stop_server EXIT
test "$(su -s /bin/sh nobody -c "$root/bin/psql -XAt -h localhost -p 55439 -d postgres -c 'SELECT 1'")" = 1
su -s /bin/sh nobody -c "$root/bin/psql -Xv ON_ERROR_STOP=1 -h /tmp/socket -p 55439 -d postgres" <<'SQL'
CREATE EXTENSION hstore;
CREATE EXTENSION vector;
CREATE COLLATION portable_icu (provider = icu, locale = 'en-US-u-kn-true', deterministic = false);
CREATE TABLE portable_probe (id integer PRIMARY KEY, properties hstore, embedding vector(3));
INSERT INTO portable_probe VALUES (1, 'a=>b', '[1,0,0]');
DO $$ BEGIN
  IF (SELECT properties->'a' FROM portable_probe WHERE id = 1) <> 'b'
     OR (SELECT embedding <-> '[1,0,0]'::vector FROM portable_probe WHERE id = 1) <> 0
     OR NOT ('2' < '10' COLLATE portable_icu) THEN
    RAISE EXCEPTION 'bundled runtime result mismatch';
  END IF;
END $$;
SQL
su -s /bin/sh nobody -c "$root/bin/pg_dumpall -h /tmp/socket -p 55439 > /tmp/portable-dump.sql"
test -s /tmp/portable-dump.sql
su -s /bin/sh nobody -c "$root/bin/pg_ctl -D /tmp/data -m fast -w stop"
trap - EXIT
printf 'PASS: bundled glibc PostgreSQL %s on %s %s\n' "$version" "$(uname -s)" "$(uname -m)"
