#!/usr/bin/env bash
set -euo pipefail

output_root=${1:?usage: windows-mingw-build.sh OUTPUT_ROOT [POSTGRESQL_VERSION] [SELECTED_POSTGRES_IMPORT_LIBRARY]}
pg_version=${2:-${PG_VERSION:-18.6}}
selected_import_lib=${3:-}
case "$pg_version" in
  15.19|16.15|17.11|18.6) ;;
  *) printf 'Unsupported PostgreSQL version: %s\n' "$pg_version" >&2; exit 2 ;;
esac
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
netcdf_root="$output_root/netcdf-no-ros3"
diagnostic_root="$output_root/dll-diagnostic"
mkdir -p "$source_root"
cd "$source_root"

curl -fL --retry 3 -o netcdf-4.10.1.tar.gz https://github.com/Unidata/netcdf-c/archive/v4.10.1/netcdf-4.10.1.tar.gz
printf '%s  %s\n' 33c27231c478c3b35da7c7758fbdd02da1fe407abcb16ddfe195f69d164f930d netcdf-4.10.1.tar.gz > netcdf-4.10.1.tar.gz.sha256
sha256sum -c netcdf-4.10.1.tar.gz.sha256
tar -xzf netcdf-4.10.1.tar.gz
cmake -S netcdf-c-4.10.1 -B netcdf-c-4.10.1/build -G Ninja \
  -DCMAKE_INSTALL_PREFIX="$netcdf_root" \
  -DBUILD_SHARED_LIBS=ON \
  -DNETCDF_ENABLE_TESTS=OFF \
  -DNETCDF_ENABLE_HDF5=ON \
  -DNETCDF_ENABLE_S3_AWS=OFF \
  -DNETCDF_ENABLE_BYTERANGE=OFF
mkdir -p "$diagnostic_root"
grep -E '^(NETCDF_ENABLE_(BYTERANGE|HDF5|S3_AWS|TESTS)|HAS_HDF5_ROS3):' \
  netcdf-c-4.10.1/build/CMakeCache.txt > "$diagnostic_root/netcdf-cmake-options.txt"
for option in \
  NETCDF_ENABLE_BYTERANGE:BOOL=OFF \
  NETCDF_ENABLE_HDF5:BOOL=ON \
  NETCDF_ENABLE_S3_AWS:BOOL=OFF \
  NETCDF_ENABLE_TESTS:BOOL=OFF; do
  grep -Fx "$option" netcdf-c-4.10.1/build/CMakeCache.txt
done
if grep -Eq '^HAS_HDF5_ROS3:INTERNAL=1$' netcdf-c-4.10.1/build/CMakeCache.txt; then
  printf 'ERROR: installed HDF5 exposed ROS3 during the NetCDF trial configuration.\n' >&2
  exit 1
fi
cmake --build netcdf-c-4.10.1/build --parallel 2
cmake --install netcdf-c-4.10.1/build
test -f "$netcdf_root/bin/libnetcdf.dll"
export PATH="$netcdf_root/bin:$PATH"
mkdir -p "$diagnostic_root"
python "$repo_root/scripts/postgis/windows-diagnose-imports.py" \
  --root "$netcdf_root/bin/libnetcdf.dll" \
  --search-directory "$netcdf_root/bin" \
  --search-directory /mingw64/bin \
  --search-directory /usr/bin \
  --output "$diagnostic_root/netcdf-import-resolution.json"
python - "$diagnostic_root/netcdf-import-resolution.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
findings = report["missing_symbols"] + report["unresolved_dlls"] + report["objdump_errors"]
if findings:
    print(json.dumps(findings, indent=2))
    raise SystemExit("NetCDF dependency resolution failed before PostgreSQL/PostGIS compilation")
PY

if test "$pg_version" = 16.15; then
  read -r source_repository source_ref source_commit source_tree < <(python - "$repo_root" "$pg_version" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'tools'))
import postgresql_git_source
source=postgresql_git_source.source_checkout(sys.argv[2], sys.argv[1])
print(source['repository'], source['ref'], source['commit'], source['tree'])
PY
)
  source_tree=${source_tree%$'\r'}
  git init "postgresql-$pg_version"
  cd "postgresql-$pg_version"
  git remote add origin "$source_repository"
  git fetch --depth=1 origin "$source_ref"
  git checkout --detach "$source_commit"
  test "$(git rev-parse HEAD^{tree})" = "$source_tree"
else
  read -r source_url source_sha < <(python - "$repo_root" "$pg_version" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'tools'))
import source_archive
source=source_archive.source_archive('postgresql', sys.argv[2], 'tar.gz', sys.argv[1])
print(source['url'], source['sha256'])
PY
)
  source_sha=${source_sha%$'\r'}
  source_archive="postgresql-$pg_version.tar.gz"
  curl -fL --retry 3 -o "$source_archive" "$source_url"
  printf '%s  %s\n' "$source_sha" "$source_archive" | sha256sum -c -
  tar -xzf "$source_archive"
  cd "postgresql-$pg_version"
fi
CC=gcc ./configure --host=x86_64-w64-mingw32 --prefix="$pgroot" --without-readline --without-zlib --without-icu --without-openssl --without-libxml --without-lz4 --without-zstd --without-ldap --without-gssapi
make -j2
make install

test "$("$pgroot/bin/pg_config.exe" --version)" = "PostgreSQL $pg_version"
if test "$pg_version" = 15.19; then
  test -f "$selected_import_lib"
  for symbol in GetNumConfigOptions MemoryContextContains; do
    nm "$selected_import_lib" | grep -Eq "[[:space:]]$symbol$"
  done
  cp "$selected_import_lib" "$pgroot/lib/libpostgres.a"
fi
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

set +x
mkdir -p "$diagnostic_root"
modules=(
  "$pgroot/lib/postgis_raster-3.dll"
  "$pgroot/bin/postgres.exe"
  "$netcdf_root/bin/libnetcdf.dll"
  /mingw64/bin/libgdal-*.dll
  /mingw64/bin/libgeos_c.dll
  /mingw64/bin/libproj-*.dll
)
for module in "${modules[@]}"; do
  test -f "$module" || continue
  report="$diagnostic_root/${module##*/}.txt"
  {
    printf 'File: %s\n' "$module"
    printf 'Direct DLL imports:\n'
    objdump -p "$module" | sed -n 's/^[[:space:]]*DLL Name: /  /p'
    printf '\nFull objdump -p import and export tables:\n'
    objdump -p "$module"
  } > "$report"
  if test "$(wc -c < "$report")" -gt 1048576; then
    head -c 1048576 "$report" > "$report.truncated"
    mv "$report.truncated" "$report"
    printf '\n[report truncated at 1 MiB]\n' >> "$report"
  fi
done
if ! python "$repo_root/scripts/postgis/windows-diagnose-imports.py" \
  --root "$pgroot/lib/postgis_raster-3.dll" \
  --search-directory "$netcdf_root/bin" \
  --search-directory "$pgroot/bin" \
  --search-directory /mingw64/bin \
  --search-directory /usr/bin \
  --output "$diagnostic_root/import-resolution.json"; then
  printf 'WARNING: focused PE import diagnostic failed; continuing with extension probe.\n'
fi

work="$output_root/cluster"
mkdir -p "$work"
"$pgroot/bin/initdb.exe" -D "$work/data" --no-locale -E UTF8 -U postgres
"$pgroot/bin/pg_ctl.exe" -D "$work/data" -l "$work/server.log" -o "-p 55438" start
finish() { "$pgroot/bin/pg_ctl.exe" -D "$work/data" -m immediate stop || true; }
trap finish EXIT
"$pgroot/bin/createdb.exe" -p 55438 postgis_probe
"$pgroot/bin/psql.exe" -X -v ON_ERROR_STOP=1 -p 55438 -d postgis_probe -f "$repo_root/scripts/postgis/probe.sql"
