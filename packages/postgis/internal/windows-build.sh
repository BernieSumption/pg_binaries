#!/usr/bin/env bash
set -euo pipefail

[[ $1 == windows && $2 == x86_64 && ${MSYSTEM:-} == MINGW64 ]]
workspace=$(cygpath -u "$3")
internal=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
prefix="$workspace/build/dependencies"
shadow="$prefix/mingw-postgresql"
sdk="$workspace/build/postgis-sdk"
jobs=${PG_BUILD_JOBS:-2}
export CC=gcc CXX=g++ AR=ar RANLIB=ranlib
export PATH="$prefix/bin:/mingw64/bin:/usr/bin"
unset PKG_CONFIG_PATH PKG_CONFIG_LIBDIR CMAKE_PREFIX_PATH CFLAGS CXXFLAGS CPPFLAGS LDFLAGS
pacman -Q | cmp - "$prefix/msys2-packages.txt" || { echo 'MSYS2 packages changed; rebuild PostGIS in a fresh workspace to refresh dependencies' >&2; exit 1; }
selected_version=$("$workspace/postgresql/bin/pg_config.exe" --version | tr -d '\r')
[[ $("$shadow/bin/pg_config.exe" --version | tr -d '\r') == "$selected_version" ]] || { echo 'MinGW PGXS and selected PostgreSQL versions differ' >&2; exit 1; }
python "$internal/windows_prepare_sdk.py" "$shadow" "$sdk"
export PATH="$sdk/bin:$PATH"
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig:/mingw64/lib/pkgconfig"
export PROJ_DATA=/mingw64/share/proj GDAL_DATA=/mingw64/share/gdal
export LDFLAGS="-L$prefix/lib" CPPFLAGS="-I$prefix/include"

cd "$workspace/sources/postgis"
./configure --prefix="$sdk" --with-pgconfig="$sdk/bin/pg_config.exe" \
  --with-gdalconfig=/mingw64/bin/gdal-config --with-geosconfig=/mingw64/bin/geos-config \
  --with-projdir=/mingw64 --with-jsondir=/mingw64 --with-protobufdir=/mingw64 \
  --with-raster --with-sfcgal="$prefix/bin/sfcgal-config" \
  --without-address-standardizer --without-tiger
make -j"$jobs"
make install
make -C "$workspace/sources/tiger_geocoder" PG_CONFIG="$sdk/bin/pg_config.exe"
make -C "$workspace/sources/tiger_geocoder" PG_CONFIG="$sdk/bin/pg_config.exe" install
python "$internal/windows_collect.py" "$sdk" "$workspace/payload" /mingw64/share
