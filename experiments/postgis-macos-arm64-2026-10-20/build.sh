#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: build.sh CORE_ARCHIVES OUTPUT_DIRECTORY TARGET_CONFIG}
output=${2:?output directory required}
target_config=${3:?resolved target config required}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
source "$repo/scripts/macos/core-prefix.sh"

selection=$(python3 - "$target_config" <<'PY'
import json, sys
from pathlib import Path
target=json.loads(Path(sys.argv[1]).read_text())
if target.get("postgresql_version") != "18.6" or target.get("architecture") != "arm64" or target.get("platform") != "macos-arm64":
    raise SystemExit("unsupported PostGIS macOS feasibility target")
core=target.get("core_archive", {})
if core.get("basename") != "postgresql-18.6-macos-arm64.tar.gz":
    raise SystemExit("resolved core archive identity mismatch")
for key in ("sha256", "run_id", "build_id", "source_revision"):
    if not core.get(key): raise SystemExit(f"resolved core lacks {key}")
print(target["postgresql_version"], target["architecture"], core["basename"], core["sha256"], core["build_id"], core["source_revision"])
PY
)
read -r pg_version architecture core_name core_sha core_build_id core_revision <<< "$selection"
core_archives=$(cd "$core_archives" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
[[ $(uname -s) == Darwin && $(uname -m) == "$architecture" ]] || { echo "Build requires native macOS $architecture" >&2; exit 1; }
core_archive="$core_archives/$core_name"
test -s "$core_archive" && (cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha" "$core_archive" | shasum -a 256 -c -
work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/postgis-macos-build.XXXXXX")
prefix_link_created=false
cleanup() { macos_remove_core_prefix; rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$work/core" "$work/source"
gdal_prefix="$work/gdal"
tar -xzf "$core_archive" -C "$work/core"
pgroot=$(cd "$work/core/postgresql" && pwd -P)
prefix=$(macos_core_prefix_from_archive "$pgroot" "$pg_version" "$architecture" "$core_build_id" "$core_revision")
macos_restore_core_prefix "$prefix" "$pgroot"
prefix_link_created=true
pg_config="$prefix/bin/pg_config"
test "$("$pg_config" --version)" = "PostgreSQL $pg_version"

export MACOSX_DEPLOYMENT_TARGET=11.0
brew_prefix=$(brew --prefix)
for tool in cmake geos-config sfcgal-config; do command -v "$tool" >/dev/null || { echo "Missing runner dependency tool: $tool" >&2; exit 1; }; done
mkdir -p "$work/gdal-source"
cd "$work/gdal-source"
curl -fL --retry 3 -o gdal.tar.gz https://download.osgeo.org/gdal/3.13.3/gdal-3.13.3.tar.gz
printf '%s  %s\n' 5e0c388d83da2d686cc00a40272882432cdb54edff43d4af173e532844a0a0ea gdal.tar.gz | shasum -a 256 -c -
tar -xzf gdal.tar.gz
cmake -S gdal-3.13.3 -B gdal-build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$gdal_prefix" \
  -DCMAKE_PREFIX_PATH="$(brew --prefix proj)" -DPROJ_ROOT="$(brew --prefix proj)" \
  -DBUILD_SHARED_LIBS=ON -DBUILD_APPS=OFF \
  -DGDAL_BUILD_OPTIONAL_DRIVERS=OFF -DOGR_BUILD_OPTIONAL_DRIVERS=OFF \
  -DGDAL_ENABLE_DRIVER_PNG=ON -DGDAL_ENABLE_DRIVER_JPEG=ON \
  -DGDAL_USE_EXTERNAL_LIBS=OFF -DGDAL_USE_INTERNAL_LIBS=ON 2>&1 | tee "$output/gdal-configure.log"
cmake --build gdal-build --parallel "$(sysctl -n hw.ncpu)" 2>&1 | tee "$output/gdal-build.log"
cmake --install gdal-build 2>&1 | tee "$output/gdal-install.log"
export PATH="$gdal_prefix/bin:$PATH"
export PKG_CONFIG_PATH="$gdal_prefix/lib/pkgconfig:$brew_prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export GDAL_DATA="$gdal_prefix/share/gdal"
export LDFLAGS="${LDFLAGS:-} -Wl,-rpath,$gdal_prefix/lib"
test -x "$gdal_prefix/bin/gdal-config"
cd "$work/source"
curl -fL --retry 3 -o postgis.tar.gz https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz
printf '%s  %s\n' ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6 postgis.tar.gz | shasum -a 256 -c -
tar -xzf postgis.tar.gz
cd postgis-3.6.4
export PKG_CONFIG_PATH="$gdal_prefix/lib/pkgconfig:$brew_prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
./configure --prefix="$pgroot" --with-pgconfig="$pg_config" --with-gdalconfig="$gdal_prefix/bin/gdal-config" \
  --with-geosconfig="$(command -v geos-config)" --with-projdir="$(brew --prefix proj)" \
  --with-jsondir="$(brew --prefix json-c)" --with-xml2config="$(brew --prefix libxml2)/bin/xml2-config" \
  --with-sfcgal="$(command -v sfcgal-config)" 2>&1 | tee "$output/configure.log"
gmake -j"$(sysctl -n hw.ncpu)" 2>&1 | tee "$output/build.log"
gmake install 2>&1 | tee "$output/install.log"

mkdir -p "$work/socket"
chmod 700 "$work/socket"
"$pgroot/bin/initdb" -D "$work/data" --no-sync >"$output/initdb.log" 2>&1
"$pgroot/bin/pg_ctl" -D "$work/data" -l "$output/postgres.log" \
  -o "-k $work/socket -p 55439" start
cleanup() {
  "$pgroot/bin/pg_ctl" -D "$work/data" -m immediate stop >/dev/null 2>&1 || true
  macos_remove_core_prefix
  rm -rf "$work"
}
trap cleanup EXIT
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55439 -d postgres \
  >"$output/raster-probe.txt" 2>&1 <<'SQL'
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_raster;
CREATE EXTENSION postgis_sfcgal;
CREATE EXTENSION postgis_topology;
SET postgis.gdal_enabled_drivers = 'GTiff PNG JPEG';
DO $$
DECLARE
  driver_count integer;
  raster_value raster;
  tiff_size integer;
  png_size integer;
  jpeg_size integer;
BEGIN
  SELECT count(*) INTO driver_count FROM ST_GDALDrivers()
  WHERE short_name IN ('GTiff', 'PNG', 'JPEG');
  IF driver_count <> 3 THEN RAISE EXCEPTION 'expected GTiff, PNG and JPEG drivers, found %', driver_count; END IF;
  raster_value := ST_AddBand(ST_MakeEmptyRaster(2, 2, 0, 2, 1, -1, 0, 0, 4326), '8BUI'::text, 128::double precision, 0::double precision);
  tiff_size := octet_length(ST_AsTIFF(raster_value));
  png_size := octet_length(ST_AsPNG(raster_value));
  jpeg_size := octet_length(ST_AsJPEG(raster_value));
  IF tiff_size <= 0 OR png_size <= 0 OR jpeg_size <= 0 THEN
    RAISE EXCEPTION 'raster serialization failed: TIFF %, PNG %, JPEG %', tiff_size, png_size, jpeg_size;
  END IF;
  RAISE NOTICE 'GTiff/PNG/JPEG drivers registered; serialized byte lengths: %, %, %', tiff_size, png_size, jpeg_size;
END $$;
SQL

python3 - "$pgroot" "$output" <<'PY'
from pathlib import Path
import sys
root, output = map(Path, sys.argv[1:])
share = root / "share/extension"
names = ("postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology")
for name in names:
    control = share / f"{name}.control"
    sql = sorted(share.glob(f"{name}--*.sql"))
    if not control.is_file() or not sql:
        raise SystemExit(f"missing installed SQL extension output for {name}")
    print(f"{name}: {len(sql)} versioned SQL files")
(output / "sql-outputs.txt").write_text("\n".join(names) + "\n")
PY

python3 "$repo/experiments/postgis-macos-arm64-2026-10-20/dependency-inventory.py" "$pgroot" "$output" "$gdal_prefix"
