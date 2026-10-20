#!/usr/bin/env bash
set -euo pipefail

core_archive=${1:?usage: cross-install-probe.sh CORE_ARCHIVE OUTPUT_ROOT}
output_root=${2:?usage: cross-install-probe.sh CORE_ARCHIVE OUTPUT_ROOT}
mkdir -p "$output_root"
output_root=$(cd "$output_root" && pwd)
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

# Build PostGIS with a matching MinGW PostgreSQL development installation.
bash "$(dirname "$0")/build-and-probe.sh" "$output_root/mingw"

exec > >(tee "$output_root/cross-install.log") 2>&1
set -x
test "${MSYSTEM:-}" = MINGW64
mkdir -p "$output_root/selected"
tar -xzf "$core_archive" -C "$output_root/selected"
selected="$output_root/selected/postgresql"
mingw="$output_root/mingw/postgresql"
test "$("$selected/bin/pg_config.exe" --version)" = 'PostgreSQL 18.6'
test "$("$mingw/bin/pg_config.exe" --version)" = 'PostgreSQL 18.6'

shopt -s nullglob
modules=("$mingw"/lib/postgis*.dll "$mingw"/lib/rtpostgis*.dll)
sql=("$mingw"/share/extension/postgis*.sql "$mingw"/share/extension/postgis*.control)
test "${#modules[@]}" -gt 0
test "${#sql[@]}" -gt 0
cp "${modules[@]}" "$selected/lib/"
cp "${sql[@]}" "$selected/share/extension/"

# This is a module-load experiment. Runtime dependency packaging is a later gate.
export PATH="$selected/bin:$mingw/bin:$mingw/lib:/mingw64/bin:$PATH"
work="$output_root/selected-cluster"
mkdir -p "$work"
"$selected/bin/initdb.exe" -D "$work/data" --no-locale -E UTF8 -U postgres
finish() { "$selected/bin/pg_ctl.exe" -D "$work/data" -m immediate stop || true; }
trap finish EXIT
"$selected/bin/pg_ctl.exe" -D "$work/data" -l "$work/server.log" -o "-p 55439 -h 127.0.0.1" start
"$selected/bin/createdb.exe" -h 127.0.0.1 -p 55439 postgis_probe
"$selected/bin/psql.exe" -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55439 -d postgis_probe \
  -f "$repo_root/scripts/postgis/probe.sql" \
  -c "CREATE TABLE cross_install_probe (id integer PRIMARY KEY, shape geometry(Point, 4326))" \
  -c "INSERT INTO cross_install_probe VALUES (1, ST_SetSRID(ST_MakePoint(1, 2), 4326))" \
  -c 'SELECT id, ST_AsText(shape) FROM cross_install_probe'
