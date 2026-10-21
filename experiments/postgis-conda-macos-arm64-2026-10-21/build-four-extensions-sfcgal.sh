#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: build-four-extensions-sfcgal.sh CORE_ARCHIVES TARGET_CONFIG CONDA_PREFIX OUTPUT}
target_config=${2:?resolved core target config required}
conda_prefix=${3:?conda environment prefix required}
output=${4:?output directory required}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
source "$repo/scripts/macos/core-prefix.sh"

selection=$(python3 - "$target_config" <<'PY'
import json, sys
target = json.load(open(sys.argv[1], encoding="utf-8"))
if (target.get("postgresql_version") != "18.6" or target.get("architecture") != "arm64"
        or target.get("platform") != "macos-arm64"):
    raise SystemExit("unsupported PostGIS conda feasibility target")
core = target.get("core_archive", {})
if core.get("basename") != "postgresql-18.6-macos-arm64.tar.gz":
    raise SystemExit("selected core archive identity mismatch")
for key in ("sha256", "build_id", "source_revision"):
    if not core.get(key):
        raise SystemExit(f"resolved core lacks {key}")
print(core["basename"], core["sha256"], core["build_id"], core["source_revision"])
PY
)
read -r core_name core_sha core_build_id core_revision <<< "$selection"
core_archives=$(cd "$core_archives" && pwd)
conda_prefix=$(cd "$conda_prefix" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo "Build requires native macOS arm64" >&2; exit 1; }
for tool in curl make python3; do command -v "$tool" >/dev/null || { echo "Missing runner tool: $tool" >&2; exit 1; }; done
for tool in cmake geos-config xml2-config; do test -x "$conda_prefix/bin/$tool" || { echo "Missing conda tool: $tool" >&2; exit 1; }; done

core_archive="$core_archives/$core_name"
test -s "$core_archive" && (cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha" "$core_archive" | shasum -a 256 -c -
work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/postgis-conda-build.XXXXXX")
prefix_link_created=false
cleanup() { macos_remove_core_prefix; rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$work/core" "$work/source" "$work/gdal-source" "$work/gdal-build" "$work/socket"
tar -xzf "$core_archive" -C "$work/core"
pgroot="$work/core/postgresql"
prefix=$(macos_core_prefix_from_archive "$pgroot" 18.6 arm64 "$core_build_id" "$core_revision")
macos_restore_core_prefix "$prefix" "$pgroot"
prefix_link_created=true
pg_config="$prefix/bin/pg_config"
test "$("$pg_config" --version)" = "PostgreSQL 18.6"

export MACOSX_DEPLOYMENT_TARGET=11.0
export PATH="$conda_prefix/bin:$PATH"
export PKG_CONFIG_PATH="$conda_prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export PROJ_DATA="$conda_prefix/share/proj"
export PROJ_LIB="$conda_prefix/share/proj"

gdal_sha256=5e0c388d83da2d686cc00a40272882432cdb54edff43d4af173e532844a0a0ea
cd "$work/gdal-source"
curl -fL --retry 3 -o gdal.tar.gz https://download.osgeo.org/gdal/3.13.3/gdal-3.13.3.tar.gz
printf '%s  %s\n' "$gdal_sha256" gdal.tar.gz | shasum -a 256 -c -
python3 - "$output/gdal-source.json" "$gdal_sha256" <<'PY'
import json, pathlib, sys
path, sha256 = pathlib.Path(sys.argv[1]), sys.argv[2]
path.write_text(json.dumps({
    "component": "GDAL",
    "version": "3.13.3",
    "source_url": "https://download.osgeo.org/gdal/3.13.3/gdal-3.13.3.tar.gz",
    "source_sha256": sha256,
}, indent=2, sort_keys=True) + "\n")
PY
tar -xzf gdal.tar.gz
gdal_prefix="$work/gdal-prefix"
cmake -S gdal-3.13.3 -B "$work/gdal-build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$gdal_prefix" \
  -DCMAKE_PREFIX_PATH="$conda_prefix" -DPROJ_ROOT="$conda_prefix" \
  -DBUILD_SHARED_LIBS=ON -DBUILD_APPS=OFF -DGDAL_BUILD_OPTIONAL_DRIVERS=OFF \
  -DOGR_BUILD_OPTIONAL_DRIVERS=OFF -DGDAL_ENABLE_DRIVER_PNG=ON -DGDAL_ENABLE_DRIVER_JPEG=ON \
  -DGDAL_USE_EXTERNAL_LIBS=OFF -DGDAL_USE_INTERNAL_LIBS=ON \
  -DGDAL_USE_PROJ=ON -DGDAL_USE_GEOS=ON 2>&1 | tee "$output/gdal-configure.log"
cmake --build "$work/gdal-build" --parallel "$(sysctl -n hw.ncpu)" 2>&1 | tee "$output/gdal-build.log"
cmake --install "$work/gdal-build" 2>&1 | tee "$output/gdal-install.log"
test -x "$gdal_prefix/bin/gdal-config"

export PG_MACOS_DEPENDENCY_PREFIX="$gdal_prefix:$conda_prefix"
export PATH="$gdal_prefix/bin:$PATH"
export PKG_CONFIG_PATH="$gdal_prefix/lib/pkgconfig:$conda_prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export GDAL_DATA="$gdal_prefix/share/gdal"
export LDFLAGS="${LDFLAGS:-} -Wl,-rpath,$gdal_prefix/lib -Wl,-rpath,$conda_prefix/lib"
export DYLD_LIBRARY_PATH="$gdal_prefix/lib:$conda_prefix/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"

cd "$work/source"
SFCGAL_COMMIT=137203dae01faab4a1287934f9457e925e3b4383
SFCGAL_SHA256=426abf9ac0de764a6098abe89c9dc84aa59273d0c5ff90819ed49a9c21f1c21f
curl -fL --retry 3 -o sfcgal.tar.gz "https://gitlab.com/SFCGAL/SFCGAL/-/archive/$SFCGAL_COMMIT/SFCGAL-$SFCGAL_COMMIT.tar.gz"
printf '%s  %s\n' "$SFCGAL_SHA256" sfcgal.tar.gz | shasum -a 256 -c -
python3 - "$output/sfcgal-source.json" "$SFCGAL_COMMIT" "$SFCGAL_SHA256" <<'PY'
import json, pathlib, sys
path, commit, sha256 = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
path.write_text(json.dumps({
    "component": "SFCGAL",
    "version": "2.3.0",
    "commit": commit,
    "source_url": f"https://gitlab.com/SFCGAL/SFCGAL/-/archive/{commit}/SFCGAL-{commit}.tar.gz",
    "source_sha256": sha256,
}, indent=2, sort_keys=True) + "\n")
PY
tar -xzf sfcgal.tar.gz
cmake -S "SFCGAL-$SFCGAL_COMMIT" -B sfcgal-build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$conda_prefix" \
  -DCMAKE_PREFIX_PATH="$conda_prefix" -DCMAKE_INSTALL_RPATH="$conda_prefix/lib" \
  -DSFCGAL_BUILD_TESTS=OFF 2>&1 | tee "$output/sfcgal-configure.log"
cmake --build sfcgal-build --parallel "$(sysctl -n hw.ncpu)" 2>&1 | tee "$output/sfcgal-build.log"
cmake --install sfcgal-build 2>&1 | tee "$output/sfcgal-install.log"
test -x "$conda_prefix/bin/sfcgal-config"

curl -fL --retry 3 -o postgis.tar.gz https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz
printf '%s  %s\n' ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6 postgis.tar.gz | shasum -a 256 -c -
tar -xzf postgis.tar.gz
cd postgis-3.6.4
./configure --prefix="$pgroot" --with-pgconfig="$pg_config" \
  --with-gdalconfig="$gdal_prefix/bin/gdal-config" \
  --with-geosconfig="$conda_prefix/bin/geos-config" \
  --with-projdir="$conda_prefix" --with-jsondir="$conda_prefix" \
  --with-xml2config="$conda_prefix/bin/xml2-config" \
  --with-sfcgal="$conda_prefix/bin/sfcgal-config" --without-protobuf \
  2>&1 | tee "$output/configure.log"
make -j"$(sysctl -n hw.ncpu)" 2>&1 | tee "$output/build.log"
make install 2>&1 | tee "$output/install.log"
python3 "$repo/experiments/postgis-conda-macos-arm64-2026-10-21/record-runtime-closure.py" \
  "$pgroot" "$conda_prefix" "$gdal_prefix" "$work" "$output" 2>&1 | tee "$output/runtime-closure.log"

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
  >"$output/sql-probe.txt" 2>&1 <<'SQL'
SELECT name FROM pg_available_extensions
WHERE name IN ('postgis', 'postgis_raster', 'postgis_sfcgal', 'postgis_topology') ORDER BY name;
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_raster;
CREATE EXTENSION postgis_sfcgal;
CREATE EXTENSION postgis_topology;
DO $$
BEGIN
  IF NOT (ST_X(ST_Transform(ST_SetSRID(ST_Point(1,0),4326),3857)) BETWEEN 111319 AND 111320) THEN
    RAISE EXCEPTION 'PROJ transform returned unexpected coordinates';
  END IF;
  IF ST_Width(ST_AsRaster(ST_SetSRID(ST_Point(0,0),4326),4,4,'8BUI',7)) <> 4 THEN
    RAISE EXCEPTION 'raster operation returned unexpected width';
  END IF;
  PERFORM topology.CreateTopology('pilot_topology',4326);
  IF postgis_sfcgal_version() IS NULL THEN
    RAISE EXCEPTION 'SFCGAL version probe returned NULL';
  END IF;
END $$;
SQL

python3 - "$pgroot/share/extension" "$output" <<'PY'
from pathlib import Path
import sys
share, output = map(Path, sys.argv[1:])
names = ("postgis", "postgis_raster", "postgis_sfcgal", "postgis_topology")
for name in names:
    if not (share / f"{name}.control").is_file():
        raise SystemExit(f"missing installed SQL extension output for {name}")
Path(output, "sql-names.txt").write_text("\n".join(names) + "\n")
PY
