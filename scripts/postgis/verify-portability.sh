#!/bin/sh
set -eu
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
case "$pg_version" in *[!0-9.]*|.*|*.) echo "Unsupported PostgreSQL version format: $pg_version" >&2; exit 2 ;; esac
case "$pg_version" in *.*) ;; *) echo "Unsupported PostgreSQL version format: $pg_version" >&2; exit 2 ;; esac
case "$pg_version" in *.*.*) echo "Unsupported PostgreSQL version format: $pg_version" >&2; exit 2 ;; esac

core=${1:?usage: verify-portability.sh CORE_ARCHIVES POSTGIS_ARCHIVES}
extension=${2:?}
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
postgis_archive=${POSTGIS_ARCHIVE_NAME:-postgis-3.6.4-postgresql-${pg_version}-linux-${architecture}.tar.gz}
case "$postgis_archive" in */*|*\\*|.|..|*[!A-Za-z0-9._-]*) echo "POSTGIS_ARCHIVE_NAME must be a basename without path separators: $postgis_archive" >&2; exit 2 ;; esac
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
test "$("$root/bin/postgres" --version)" = "postgres (PostgreSQL) $pg_version"
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
