#!/bin/sh
set -eu

core=${1:?usage: verify-portability.sh CORE_ARCHIVES POSTGIS_ARCHIVES}
extension=${2:?}
pg_archive=postgresql-18.6-linux-x86_64.tar.gz
postgis_archive=postgis-3.6.4-postgresql-18.6-linux-x86_64.tar.gz
cd "$core"
sha256sum -c "$pg_archive.sha256"
cd "$extension"
sha256sum -c "$postgis_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/postgis /tmp/data /tmp/socket
tar -xzf "$core/$pg_archive" -C /tmp/first
tar -xzf "$extension/$postgis_archive" -C /tmp/postgis
cp -a /tmp/postgis/postgis/. /tmp/first/postgresql/
mv /tmp/first/postgresql /tmp/moved/postgresql
root=/tmp/moved/postgresql
test ! -e /tmp/first/postgresql
test "$("$root/bin/postgres" --version)" = 'postgres (PostgreSQL) 18.6'
export PROJ_LIB="$root/share/proj" PROJ_DATA="$root/share/proj" GDAL_DATA="$root/share/gdal"
chown nobody /tmp/data /tmp/socket
su -s /bin/sh nobody -c "$root/bin/initdb -D /tmp/data --encoding=UTF8 --locale=C --no-instructions"
su -s /bin/sh nobody -c "$root/bin/pg_ctl -D /tmp/data -o '-k /tmp/socket -p 55443 -h 127.0.0.1' -w start"
stop_server() {
  su -s /bin/sh nobody -c "$root/bin/pg_ctl -D /tmp/data -m immediate stop" >/dev/null 2>&1 || true
}
trap stop_server EXIT
su -s /bin/sh nobody -c "$root/bin/psql -Xv ON_ERROR_STOP=1 -h /tmp/socket -p 55443 -d postgres -f /repo/scripts/postgis/probe.sql"
su -s /bin/sh nobody -c "$root/bin/pg_dumpall -h /tmp/socket -p 55443 > /tmp/postgis-dump.sql"
test -s /tmp/postgis-dump.sql
su -s /bin/sh nobody -c "$root/bin/pg_ctl -D /tmp/data -m fast -w stop"
trap - EXIT
printf 'PASS: relocated PostgreSQL and PostGIS archives on %s %s\n' "$(uname -s)" "$(uname -m)"
