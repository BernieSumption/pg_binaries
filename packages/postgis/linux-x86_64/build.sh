#!/usr/bin/env bash
set -euo pipefail

[[ $# == 8 ]] || { echo "usage: $0 POSTGIS_URL POSTGIS_SHA256 POSTGIS_VERSION TIGER_URL TIGER_SHA256 TIGER_VERSION POSTGRESQL_PREFIX OUTPUT_DIR" >&2; exit 2; }
postgis_url=$1 postgis_sha=$2 postgis_version=$3
tiger_url=$4 tiger_sha=$5 tiger_version=$6
pg=$7 output_dir=$8
[[ $postgis_sha =~ ^[0-9a-f]{64}$ && $tiger_sha =~ ^[0-9a-f]{64}$ ]] || { echo 'Invalid source SHA-256' >&2; exit 2; }
[[ $postgis_version =~ ^[0-9]+(\.[0-9]+)+$ && $tiger_version =~ ^[0-9]+(\.[0-9]+)+$ ]] || { echo 'Invalid source version' >&2; exit 2; }
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || { echo 'This recipe requires Linux x86_64' >&2; exit 1; }
[[ -x $pg/bin/pg_config ]] || { echo 'Missing PostgreSQL pg_config' >&2; exit 1; }
pg=$(cd "$pg" && pwd)
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
pg_version=$($pg/bin/pg_config --version | sed 's/^PostgreSQL //')
installed_prefix=$(dirname "$($pg/bin/pg_config --bindir)")
[[ $installed_prefix == /* ]] || { echo 'PostgreSQL install prefix must be absolute' >&2; exit 1; }
work=$(mktemp -d "${TMPDIR:-/tmp}/postgis.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/source" "$work/stage" "$work/payload/postgresql/lib/postgis-deps"
stage="$work/payload/postgresql"

fetch() {
  local url=$1 sha=$2 path=$3
  curl --fail --location --retry 3 --silent --show-error "$url" --output "$path"
  printf '%s  %s\n' "$sha" "$path" | sha256sum --check --status || { echo "Source checksum mismatch: $path" >&2; exit 1; }
}
fetch "$postgis_url" "$postgis_sha" "$work/source/postgis.tar.gz"
fetch "$tiger_url" "$tiger_sha" "$work/source/tiger.tar.gz"
tar -xzf "$work/source/postgis.tar.gz" -C "$work/source"
tar -xzf "$work/source/tiger.tar.gz" -C "$work/source"
postgis_source="$work/source/postgis-$postgis_version"
tiger_source="$work/source/postgis_tiger_geocoder"
[[ -d $postgis_source && -d $tiger_source ]] || { echo 'Selected PostGIS or TIGER source directory is missing' >&2; exit 1; }

export PATH="$pg/bin:$PATH"
export PROJ_DATA=/usr/share/proj PROJ_LIB=/usr/share/proj GDAL_DATA=/usr/share/gdal
cd "$postgis_source"
./configure --prefix="$pg" --with-pgconfig="$pg/bin/pg_config" \
  --with-gdalconfig=/usr/bin/gdal-config --with-geosconfig=/usr/bin/geos-config \
  --with-projdir=/usr --with-jsondir=/usr --with-raster \
  --with-sfcgal=/usr/bin/sfcgal-config --with-protobufdir=/usr
make -j"$(nproc)"
make install DESTDIR="$work/stage"
make -C "$tiger_source" PG_CONFIG="$pg/bin/pg_config"
make -C "$tiger_source" PG_CONFIG="$pg/bin/pg_config" DESTDIR="$work/stage" install

python3 - "$stage" "$work/stage$installed_prefix" <<'PY'
from pathlib import Path
import shutil
import sys

stage = Path(sys.argv[1])
(stage / 'share/extension').mkdir(parents=True, exist_ok=True)
(stage / 'lib').mkdir(parents=True, exist_ok=True)
installed = Path(sys.argv[2])
names = ('postgis', 'postgis_raster', 'postgis_sfcgal', 'postgis_topology', 'postgis_tiger_geocoder')
for name in names:
    control = installed / 'share/extension' / f'{name}.control'
    if not control.is_file():
        raise SystemExit(f'Missing extension control file: {control}')
    shutil.copy2(control, stage / 'share/extension' / control.name)
    sqls = list((installed / 'share/extension').glob(f'{name}--*.sql'))
    if not sqls:
        raise SystemExit(f'Missing SQL files for {name}')
    for sql in sqls:
        shutil.copy2(sql, stage / 'share/extension' / sql.name)
modules = ('postgis-3', 'postgis_raster-3', 'postgis_sfcgal-3', 'postgis_topology-3')
for name in modules:
    source = installed / 'lib' / f'{name}.so'
    if not source.is_file():
        raise SystemExit(f'Missing PostGIS module: {source}')
    shutil.copy2(source, stage / 'lib' / source.name)
for directory in ('proj', 'gdal'):
    source = Path('/usr/share') / directory
    target = stage / 'share' / directory
    if not source.is_dir():
        raise SystemExit(f'Missing runtime data: {source}')
    shutil.copytree(source, target, symlinks=True)
PY

for pass in 1 2 3 4 5; do
  while IFS= read -r -d '' elf; do
    file -b "$elf" | grep -q ELF || continue
    while read -r library path; do
      [[ -f $path ]] || { echo "Unresolved runtime dependency $library for $elf" >&2; exit 1; }
      case "$library" in linux-vdso*|ld-linux*|libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|libresolv.so*|libnss_*|libpq.so*) continue ;; esac
      case "$path" in "$pg"/lib/*|"$stage"/lib/*) continue ;; esac
      dest="$stage/lib/postgis-deps/$library"
      [[ -e $dest ]] || cp -L "$path" "$dest"
    done < <(ldd "$elf" | awk '$2 == "=>" {print $1, $3}')
  done < <(find "$stage/lib" -type f -print0)
done
while IFS= read -r -d '' elf; do
  file -b "$elf" | grep -q ELF || continue
  case "$elf" in */postgis-deps/*) patchelf --set-rpath '$ORIGIN' "$elf" ;; *) patchelf --set-rpath '$ORIGIN:$ORIGIN/postgis-deps' "$elf" ;; esac
done < <(find "$stage/lib" -type f -print0)

printf '%s\n' 'See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md' > "$stage/LICENCE"
cd "$work/payload"
archive="postgis-postgresql-${pg_version}-linux-x86_64.tar.gz"
tar -czf "$output_dir/$archive" postgresql
sha256sum "$output_dir/$archive" > "$output_dir/$archive.sha256"
echo "$output_dir/$archive"
