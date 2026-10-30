#!/usr/bin/env bash
set -euo pipefail

workspace=$3
internal=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
pg="$workspace/postgresql"
stage="$workspace/build/stage"
dependencies="$workspace/build/dependencies"
patchelf_source="$workspace/sources/patchelf"
patchelf_build="$workspace/build/patchelf-build"
patchelf_prefix="$dependencies/tools"
export PATH="$pg/bin:$PATH"
export PROJ_DATA=/usr/share/proj PROJ_LIB=/usr/share/proj GDAL_DATA=/usr/share/gdal

mkdir -p "$patchelf_build"
(
  cd "$patchelf_build"
  "$patchelf_source/configure" --prefix="$patchelf_prefix"
  make -j"$(nproc)"
  make install
)
patchelf="$patchelf_prefix/bin/patchelf"

gdal_libdir=$(pkg-config --variable=libdir gdal)
gdal_link="$gdal_libdir/libgdal.so"
gdal_real=$(readlink -f "$gdal_link")
gdal_soname=$("$patchelf" --print-soname "$gdal_real")
[[ $gdal_soname == libgdal.so.* ]] || { echo "Unexpected GDAL SONAME: $gdal_soname" >&2; exit 1; }
mkdir -p "$dependencies/lib"
gdal_private="$dependencies/lib/$gdal_soname"
# Patch a dereferenced private copy so the distro's GDAL library stays unchanged.
cp --dereference "$gdal_link" "$gdal_private"

gdal_undefined_symbols=$(nm -D --undefined-only "$gdal_private")
gdal_defined_symbols=$(nm -D --defined-only "$gdal_private")
for symbol in lo_read lo_write; do
  if ! grep -E "[[:space:]]${symbol}$" <<< "$gdal_undefined_symbols" >/dev/null; then
    echo "GDAL does not import expected libpq symbol: $symbol" >&2
    exit 1
  fi
  if grep -E "[[:space:]]${symbol}$" <<< "$gdal_defined_symbols" >/dev/null; then
    echo "GDAL defines unexpected libpq symbol: $symbol" >&2
    exit 1
  fi
done
# Bind GDAL's large-object calls to PostgreSQL's namespaced compatibility exports.
symbol_map="$workspace/build/gdal-symbol-map.txt"
printf '%s\n' \
  'lo_read pg_binaries_libpq_lo_read' \
  'lo_write pg_binaries_libpq_lo_write' > "$symbol_map"
"$patchelf" --rename-dynamic-symbols "$symbol_map" "$gdal_private"

# Use the distro's shared geospatial libraries. Static linking would require
# rebuilding their dependencies and preserving GDAL's driver configuration.
cd "$workspace/sources/postgis"
./configure --prefix="$pg" --with-pgconfig="$pg/bin/pg_config" \
  --with-gdalconfig=/usr/bin/gdal-config --with-geosconfig=/usr/bin/geos-config \
  --with-projdir=/usr --with-jsondir=/usr --with-raster \
  --with-sfcgal=/usr/bin/sfcgal-config --with-protobufdir=/usr \
  --without-address-standardizer --without-tiger
make -j"$(nproc)"
make install DESTDIR="$stage"
make -C "$workspace/sources/tiger_geocoder" PG_CONFIG="$pg/bin/pg_config"
make -C "$workspace/sources/tiger_geocoder" PG_CONFIG="$pg/bin/pg_config" DESTDIR="$stage" install

python3 "$internal/collect.py" "$stage" "$pg" "$workspace/payload" /usr/share .so
