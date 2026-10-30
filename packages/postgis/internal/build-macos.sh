#!/usr/bin/env bash
set -euo pipefail

arch=$2 workspace=$3
internal=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
pg="$workspace/postgresql"
work="$workspace/build"
deps="$work/dependencies"
tools="$work/tools"
mkdir -p "$tools"
bash "$internal/dependencies-macos.sh" "$arch" "$workspace"

[[ $("$deps/bin/xml2-config" --version) == 2.15.4 ]] || { echo 'PostGIS libxml2 version differs from PostgreSQL' >&2; exit 1; }
[[ -f "$pg/lib/libxml2.16.dylib" ]] || { echo 'PostgreSQL lacks libxml2.16.dylib' >&2; exit 1; }
ln -s "$deps/bin/protoc-gen-c" "$tools/protoc-c"
export POSTGIS_DEPS_PREFIX="$deps" POSTGIS_PG_PREFIX="$pg"
# Use PostgreSQL's libxml2 so both projects load the same copy.
cat > "$tools/xml2-config" <<'SH'
#!/usr/bin/env bash
case "${1:-}" in
  --libs) printf '%s -lz -liconv\n' "$POSTGIS_PG_PREFIX/lib/libxml2.16.dylib" ;;
  *) exec "$POSTGIS_DEPS_PREFIX/bin/xml2-config" "$@" ;;
esac
SH
chmod +x "$tools/xml2-config"

if [[ $arch == x86_64 ]]; then
  cat > "$tools/xsltproc" <<'SH'
#!/usr/bin/env bash
unset DYLD_LIBRARY_PATH
exec /usr/bin/xsltproc "$@"
SH
  chmod +x "$tools/xsltproc"
  export XSLTPROC="$tools/xsltproc"
fi

export PATH="$tools:$deps/bin:$PATH"
export PKG_CONFIG_PATH="$deps/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export PROJ_DATA="$deps/share/proj" PROJ_LIB="$deps/share/proj" GDAL_DATA="$deps/share/gdal"
export DYLD_LIBRARY_PATH="$deps/lib:$pg/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
export CPPFLAGS="-I$deps/include${CPPFLAGS:+ $CPPFLAGS}"
export LDFLAGS="-Wl,-headerpad_max_install_names -Wl,-rpath,$deps/lib -L$deps/lib -Wl,-rpath,$pg/lib -L$pg/lib${LDFLAGS:+ $LDFLAGS}"

cd "$workspace/sources/postgis"
./configure --prefix="$pg" --with-pgconfig="$pg/bin/pg_config" \
  --with-gdalconfig="$deps/bin/gdal-config" --with-geosconfig="$deps/bin/geos-config" \
  --with-projdir="$deps" --with-jsondir="$deps" --with-xml2config="$tools/xml2-config" \
  --with-sfcgal="$deps/bin/sfcgal-config" --with-raster --with-protobufdir="$deps" \
  --without-address-standardizer --without-tiger
# PGXS puts these flags before PostgreSQL's inherited system-library paths.
pg_ldflags="-L$deps/lib${PG_LDFLAGS:+ $PG_LDFLAGS}"
make PG_LDFLAGS="$pg_ldflags" -j"$(sysctl -n hw.ncpu)"
stage="$work/stage"
make PG_LDFLAGS="$pg_ldflags" install DESTDIR="$stage"
make -C "$workspace/sources/tiger_geocoder" PG_CONFIG="$pg/bin/pg_config" PG_LDFLAGS="$pg_ldflags"
make -C "$workspace/sources/tiger_geocoder" PG_CONFIG="$pg/bin/pg_config" PG_LDFLAGS="$pg_ldflags" DESTDIR="$stage" install

python3 "$internal/collect.py" "$stage" "$pg" "$workspace/payload" "$deps/share" .dylib
