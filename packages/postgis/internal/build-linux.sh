#!/usr/bin/env bash
set -euo pipefail

workspace=$3
internal=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
pg="$workspace/postgresql"
stage="$workspace/build/stage"
export PATH="$pg/bin:$PATH"
export PROJ_DATA=/usr/share/proj PROJ_LIB=/usr/share/proj GDAL_DATA=/usr/share/gdal

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
