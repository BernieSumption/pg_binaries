#!/usr/bin/env bash
set -euo pipefail

output_root=${1:?usage: build-and-probe.sh OUTPUT_ROOT}
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
mkdir -p "$output_root"
output_root=$(cd "$output_root" && pwd)
exec > >(tee "$output_root/build.log") 2>&1
set -x

test "${MSYSTEM:-}" = MINGW64
printf 'int main(void) { return 0; }\n' > "$output_root/compiler-test.c"
gcc -v "$output_root/compiler-test.c" -o "$output_root/compiler-test.exe"
"$output_root/compiler-test.exe"
source_root="$output_root/source"
pgroot="$output_root/postgresql"
mkdir -p "$source_root"
cd "$source_root"

curl -fL --retry 3 -o postgresql-18.6.tar.bz2 https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2
printf '%s  %s\n' 555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f postgresql-18.6.tar.bz2 | sha256sum -c -
tar -xjf postgresql-18.6.tar.bz2
cd postgresql-18.6
CC=gcc ./configure --host=x86_64-w64-mingw32 --prefix="$pgroot" --without-readline --without-zlib --without-icu --without-openssl --without-libxml --without-lz4 --without-zstd --without-ldap --without-gssapi
make -j2
make install

test "$("$pgroot/bin/pg_config.exe" --version)" = 'PostgreSQL 18.6'
cd "$source_root"
curl -fL --retry 3 -o postgis-3.6.4.tar.gz https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz
printf '%s  %s\n' ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6 postgis-3.6.4.tar.gz | sha256sum -c -
tar -xzf postgis-3.6.4.tar.gz
cd postgis-3.6.4
export PATH="$pgroot/bin:$PATH"
export PG_CONFIG="$pgroot/bin/pg_config.exe"
./configure --with-pgconfig="$PG_CONFIG" --with-sfcgal=/mingw64/bin/sfcgal-config --without-tiger --without-protobuf
make
make install

{
  shopt -s nocasematch
  printf 'PATH=%s\n' "$PATH"
  modules=("$pgroot"/lib/postgis_raster-3.dll /mingw64/bin/gdal*.dll)
  for module in "${modules[@]}"; do
    test -f "$module" || continue
    printf '\n=== %s ===\n' "$module"
    imports=$(objdump -p "$module" | sed -n 's/^[[:space:]]*DLL Name: //p')
    printf '%s\n' "$imports"
    while IFS= read -r dll; do
      test -n "$dll" || continue
      printf 'Candidates for %s:\n' "$dll"
      for path_dir in "$pgroot/bin" /mingw64/bin; do
        for candidate in "$path_dir"/*; do
          if [[ -f "$candidate" && "${candidate##*/}" == "$dll" ]]; then
            printf '  %s\n' "$candidate"
          fi
        done
      done
    done <<< "$imports"
  done
} 2>&1 | tee "$output_root/dll-diagnostic.log"

work="$output_root/cluster"
mkdir -p "$work"
"$pgroot/bin/initdb.exe" -D "$work/data" --no-locale -E UTF8 -U postgres
"$pgroot/bin/pg_ctl.exe" -D "$work/data" -l "$work/server.log" -o "-p 55438" start
finish() { "$pgroot/bin/pg_ctl.exe" -D "$work/data" -m immediate stop || true; }
trap finish EXIT
"$pgroot/bin/createdb.exe" -p 55438 postgis_probe
"$pgroot/bin/psql.exe" -X -v ON_ERROR_STOP=1 -p 55438 -d postgis_probe -f "$repo_root/scripts/postgis/probe.sql"
