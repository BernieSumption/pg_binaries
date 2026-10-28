#!/usr/bin/env bash
set -euo pipefail

pg_version=${POSTGRESQL_VERSION:?}
postgis_url=${POSTGIS_URL:?}
postgis_sha=${POSTGIS_SHA256:?}
tiger_url=${TIGER_URL:?}
tiger_sha=${TIGER_SHA256:?}
[[ $postgis_sha =~ ^[0-9a-f]{64}$ && $tiger_sha =~ ^[0-9a-f]{64}$ ]] || { echo 'Invalid source SHA-256' >&2; exit 2; }
rm -rf /work/stage
mkdir -p /work/pg /work/source /work/stage/postgresql/lib/postgis-deps /out
tar -xzf /input/postgresql-development.tar.gz -C /work/pg
[[ -x /work/pg/postgresql/bin/pg_config ]] || { echo 'Development archive must contain postgresql/bin/pg_config' >&2; exit 1; }
rm -rf /opt/postgresql
mv /work/pg/postgresql /opt/postgresql
pg=/opt/postgresql
[[ $($pg/bin/pg_config --version) == "PostgreSQL $pg_version" ]] || { echo 'PostgreSQL development archive version mismatch' >&2; exit 1; }
stage=/work/stage/postgresql

fetch() {
  local url=$1 sha=$2 path=$3
  curl --fail --location --retry 3 --silent --show-error "$url" --output "$path"
  printf '%s  %s\n' "$sha" "$path" | sha256sum --check --status || { echo "Source checksum mismatch: $path" >&2; exit 1; }
}
fetch "$postgis_url" "$postgis_sha" /work/source/postgis.tar.gz
fetch "$tiger_url" "$tiger_sha" /work/source/tiger.tar.gz
tar -xzf /work/source/postgis.tar.gz -C /work/source
tar -xzf /work/source/tiger.tar.gz -C /work/source
postgis_source=$(find /work/source -mindepth 1 -maxdepth 1 -type d -name 'postgis-3.6.4')
tiger_source=$(find /work/source -mindepth 1 -maxdepth 1 -type d -name 'postgis_tiger_geocoder')

export PATH="$pg/bin:$PATH"
export PKG_CONFIG_PATH=/usr/lib/aarch64-linux-gnu/pkgconfig
export PROJ_DATA=/usr/share/proj PROJ_LIB=/usr/share/proj GDAL_DATA=/usr/share/gdal
cd "$postgis_source"
./configure --prefix="$pg" --with-pgconfig="$pg/bin/pg_config" \
  --with-gdalconfig=/usr/bin/gdal-config --with-geosconfig=/usr/bin/geos-config \
  --with-projdir=/usr --with-jsondir=/usr --with-raster \
  --with-sfcgal=/usr/bin/sfcgal-config --with-protobufdir=/usr
make -j"$(nproc)"
make install DESTDIR=/work/stage
make -C "$tiger_source" PG_CONFIG="$pg/bin/pg_config"
make -C "$tiger_source" PG_CONFIG="$pg/bin/pg_config" DESTDIR=/work/stage install

python3 - <<'PY'
from pathlib import Path
import shutil

stage = Path('/work/stage/postgresql')
(stage / 'share/extension').mkdir(parents=True, exist_ok=True)
(stage / 'lib').mkdir(parents=True, exist_ok=True)
installed = Path('/work/stage/opt/postgresql')
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
shutil.rmtree('/work/stage/opt', ignore_errors=True)
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
cd /work/stage
archive="postgis-postgresql-${pg_version}-linux-arm64.tar.gz"
tar -czf "/out/$archive" postgresql
cd /out
sha256sum "$archive" > "$archive.sha256"
echo "Built /out/$archive"
