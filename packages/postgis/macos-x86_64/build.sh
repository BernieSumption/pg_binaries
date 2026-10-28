#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 8 ]]; then
  echo "usage: $0 POSTGIS_URL POSTGIS_SHA VERSION TIGER_URL TIGER_SHA TIGER_VERSION POSTGRESQL_PREFIX OUTPUT_DIR" >&2
  exit 2
fi
postgis_url=$1
postgis_sha=$2
version=$3
tiger_url=$4
tiger_sha=$5
tiger_version=$6
pg=$7
output_dir=$8

[[ $(uname -s) == Darwin && $(uname -m) == x86_64 ]] || { echo 'This recipe requires macOS x86_64' >&2; exit 1; }
: "${MACOSX_DEPLOYMENT_TARGET:?Set the selected minimum macOS version}"
[[ -x "$pg/bin/pg_config" ]] || { echo "Missing PostgreSQL development installation: $pg" >&2; exit 1; }
for sha in "$postgis_sha" "$tiger_sha"; do
  [[ $sha =~ ^[0-9a-f]{64}$ ]] || { echo 'Source SHA-256 must be 64 lowercase hex digits' >&2; exit 2; }
done
pg=$(cd "$pg" && pwd)
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
work=${POSTGIS_WORK_DIR:-$(dirname "$output_dir")/postgis-work}
mkdir -p "$work" "$work/tools"
work=$(cd "$work" && pwd)

deps=${POSTGIS_DEPENDENCY_PREFIX:-$work/dependencies}
if [[ -z ${POSTGIS_DEPENDENCY_PREFIX:-} ]]; then
  "$repo_root/packages/postgis/macos-x86_64/build-dependencies.sh" "$deps"
fi
deps=$(cd "$deps" && pwd)
for tool in cmake gdal-config geos-config sfcgal-config xml2-config protoc-gen-c; do
  [[ -x "$deps/bin/$tool" ]] || { echo "Missing PostGIS dependency tool: $tool" >&2; exit 1; }
done
[[ $("$deps/bin/xml2-config" --version) == 2.15.4 ]] || { echo 'PostGIS libxml2 version differs from PostgreSQL' >&2; exit 1; }
[[ -f "$pg/lib/libxml2.16.dylib" ]] || { echo 'PostgreSQL lacks libxml2.16.dylib' >&2; exit 1; }

download() {
  local url=$1 expected=$2 archive=$3
  if [[ ! -f "$archive" ]]; then
    curl --fail --location --retry 3 --silent --show-error "$url" --output "$archive"
  fi
  local actual
  actual=$(shasum -a 256 "$archive" | awk '{print $1}')
  [[ "$actual" == "$expected" ]] || { echo "Source checksum mismatch: $archive" >&2; exit 1; }
}
download "$postgis_url" "$postgis_sha" "$work/postgis-$version.tar.gz"
download "$tiger_url" "$tiger_sha" "$work/postgis_tiger_geocoder-$tiger_version.tar.gz"
if [[ ! -d "$work/postgis-$version" ]]; then
  tar -xzf "$work/postgis-$version.tar.gz" -C "$work"
fi
if [[ ! -d "$work/postgis_tiger_geocoder" ]]; then
  tar -xzf "$work/postgis_tiger_geocoder-$tiger_version.tar.gz" -C "$work"
fi

ln -sf "$deps/bin/protoc-gen-c" "$work/tools/protoc-c"
export POSTGIS_DEPS_PREFIX="$deps" POSTGIS_PG_PREFIX="$pg"
cat > "$work/tools/xml2-config" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  --cflags) exec "$POSTGIS_DEPS_PREFIX/bin/xml2-config" --cflags ;;
  --libs) printf '%s -lz -liconv\n' "$POSTGIS_PG_PREFIX/lib/libxml2.16.dylib" ;;
  --version) exec "$POSTGIS_DEPS_PREFIX/bin/xml2-config" --version ;;
  *) exec "$POSTGIS_DEPS_PREFIX/bin/xml2-config" "$@" ;;
esac
EOF
chmod +x "$work/tools/xml2-config"

export PATH="$work/tools:$deps/bin:$PATH"
export PKG_CONFIG_PATH="$deps/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export PROJ_DATA="$deps/share/proj" PROJ_LIB="$deps/share/proj" GDAL_DATA="$deps/share/gdal"
export DYLD_LIBRARY_PATH="$deps/lib:$pg/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
export CPPFLAGS="-I$deps/include${CPPFLAGS:+ $CPPFLAGS}"
export LDFLAGS="-Wl,-headerpad_max_install_names -Wl,-rpath,$deps/lib -L$deps/lib -Wl,-rpath,$pg/lib -L$pg/lib${LDFLAGS:+ $LDFLAGS}"

jobs=$(sysctl -n hw.ncpu)
cd "$work/postgis-$version"
./configure --prefix="$pg" --with-pgconfig="$pg/bin/pg_config" \
  --with-gdalconfig="$deps/bin/gdal-config" --with-geosconfig="$deps/bin/geos-config" \
  --with-projdir="$deps" --with-jsondir="$deps" --with-xml2config="$work/tools/xml2-config" \
  --with-sfcgal="$deps/bin/sfcgal-config" --with-raster --with-protobufdir="$deps" \
  --without-address-standardizer --without-tiger
make -j"$jobs"
stage="$work/stage"
rm -rf "$stage"
make install DESTDIR="$stage"
make -C "$work/postgis_tiger_geocoder" PG_CONFIG="$pg/bin/pg_config"
make -C "$work/postgis_tiger_geocoder" PG_CONFIG="$pg/bin/pg_config" DESTDIR="$stage" install

staged_pg="$stage$pg"
payload="$work/payload/postgresql"
rm -rf "$work/payload"
mkdir -p "$payload/lib" "$payload/share/extension"
for module in postgis-3 postgis_raster-3 postgis_sfcgal-3 postgis_topology-3; do
  [[ -f "$staged_pg/lib/$module.dylib" ]] || { echo "Missing staged PostGIS module: $module" >&2; exit 1; }
  cp "$staged_pg/lib/$module.dylib" "$payload/lib/"
done
cp "$staged_pg"/share/extension/postgis* "$payload/share/extension/"
for extension in postgis postgis_raster postgis_sfcgal postgis_topology postgis_tiger_geocoder; do
  [[ -f "$payload/share/extension/$extension.control" ]] || { echo "Missing staged control file: $extension" >&2; exit 1; }
done

python3 "$repo_root/platforms/macos/bundle.py" "$payload" "$deps" postgis-deps
python3 "$repo_root/verification/macos/static.py" "$payload" macos-x86_64
cp -R "$deps/share/proj" "$payload/share/proj"
cp -R "$deps/share/gdal" "$payload/share/gdal"
printf '%s\n' 'See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md' > "$payload/LICENCE"

pg_version=$("$pg/bin/pg_config" --version)
pg_version=${pg_version#PostgreSQL }
archive="postgis-postgresql-$pg_version-macos-x86_64.tar.gz"
export COPYFILE_DISABLE=1
tar -C "$work/payload" -czf "$output_dir/$archive" postgresql
shasum -a 256 "$output_dir/$archive" > "$output_dir/$archive.sha256"
echo "$output_dir/$archive"
