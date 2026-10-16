#!/usr/bin/env bash
set -euo pipefail
pg_version=${1:?}
pg_archive=${2:?}
vector_archive=${3:?}
case "$pg_version" in 15.*|16.*|17.*|18.*) ;; *) exit 2 ;; esac

kernel=$(uname -r)
printf 'guest_os='; . /etc/os-release; printf '%s\n' "$PRETTY_NAME"
printf 'guest_kernel=%s\n' "$kernel"
[[ $kernel =~ ^5\.15\. ]] || { echo "Expected Linux 5.15, got $kernel" >&2; exit 1; }

mkdir -p /tmp/pg-binaries/postgresql /tmp/pg-binaries/vector
tar -xzf "/tmp/$pg_archive" -C /tmp/pg-binaries
tar -xzf "/tmp/$vector_archive" -C /tmp/pg-binaries/vector
cp -a /tmp/pg-binaries/vector/pgvector/. /tmp/pg-binaries/postgresql/
prefix=/tmp/pg-binaries/postgresql
test "$("$prefix/bin/postgres" --version)" = "postgres (PostgreSQL) $pg_version"

if ! id postgres >/dev/null 2>&1; then
  sudo useradd --create-home postgres
fi
sudo install -d -o postgres -g postgres /tmp/pg-binaries/data /tmp/pg-binaries/socket
sudo -u postgres "$prefix/bin/initdb" -D /tmp/pg-binaries/data --encoding=UTF8 --locale=C --no-instructions
sudo -u postgres "$prefix/bin/pg_ctl" -D /tmp/pg-binaries/data \
  -o '-k /tmp/pg-binaries/socket -p 55430 -h ""' -w start
cleanup() {
  sudo -u postgres "$prefix/bin/pg_ctl" -D /tmp/pg-binaries/data -m immediate stop >/dev/null 2>&1 || true
}
trap cleanup EXIT

sudo -u postgres "$prefix/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/pg-binaries/socket -p 55430 -d postgres <<SQL
CREATE EXTENSION vector;
CREATE TABLE endpoint_probe (embedding vector(3));
INSERT INTO endpoint_probe VALUES ('[1,0,0]'), ('[0,1,0]');
DO \$\$ BEGIN
  IF (SELECT embedding <-> '[1,0,0]'::vector FROM endpoint_probe ORDER BY embedding <-> '[1,0,0]'::vector LIMIT 1) <> 0 THEN
    RAISE EXCEPTION 'pgvector result mismatch';
  END IF;
END \$\$;
SQL
sudo -u postgres "$prefix/bin/pg_ctl" -D /tmp/pg-binaries/data -m fast -w stop
trap - EXIT
echo "PASS: PostgreSQL $pg_version and pgvector on Ubuntu 22.04 Linux $kernel"
