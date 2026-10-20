#!/usr/bin/env bash
set -euo pipefail

core_archive=${1:?usage: selected-core-probe.sh CORE_ARCHIVE OUTPUT_ROOT}
output_root=${2:?usage: selected-core-probe.sh CORE_ARCHIVE OUTPUT_ROOT}
mkdir -p "$output_root/core"
tar -xzf "$core_archive" -C "$output_root/core"
output_root=$(cd "$output_root" && pwd)
exec > >(tee "$output_root/build.log") 2>&1
set -x

test "${MSYSTEM:-}" = MINGW64
pgroot="$output_root/core/postgresql"
pgconfig="$pgroot/bin/pg_config.exe"
test -f "$pgroot/lib/postgres.lib"
test -f "$pgroot/lib/libpq.lib"
test "$("$pgconfig" --version)" = 'PostgreSQL 18.6'
for import_library in "$pgroot"/lib/*.lib; do
  test -f "$import_library" || continue
  cp "$import_library" "${import_library%.lib}.a"
done
source_root="$output_root/source"
mkdir -p "$source_root"
cd "$source_root"
curl -fL --retry 3 -o postgis-3.6.4.tar.gz https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz
printf '%s  %s\n' ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6 postgis-3.6.4.tar.gz | sha256sum -c -
tar -xzf postgis-3.6.4.tar.gz
cd postgis-3.6.4

export PATH="$(cygpath -u "$pgroot/bin"):$PATH"
export REAL_PG_CONFIG="$(cygpath -u "$pgconfig")"
cat > "$output_root/pg_config-gcc" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  --cc) printf '%s\n' gcc ;;
  --cflags) printf '%s\n' -O2 ;;
  --cppflags|--ldflags) printf '\n' ;;
  *) exec "$REAL_PG_CONFIG" "$@" ;;
esac
EOF
chmod +x "$output_root/pg_config-gcc"
export PG_CONFIG="$output_root/pg_config-gcc"
./configure --with-pgconfig="$PG_CONFIG" --without-raster --without-tiger --without-topology --without-sfcgal --without-protobuf
cat > "$output_root/gcc-pgxs" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
args=()
for arg in "$@"; do
  case "$arg" in
    /wd[0-9]*) ;;
    /D*) args+=("-D${arg#/D}") ;;
    *) args+=("$arg") ;;
  esac
done
exec gcc "${args[@]}"
EOF
chmod +x "$output_root/gcc-pgxs"
make CC="$output_root/gcc-pgxs"
make CC="$output_root/gcc-pgxs" install

work="$output_root/cluster"
mkdir -p "$work"
"$pgroot/bin/initdb.exe" -D "$work/data" --no-locale -E UTF8 -U postgres
"$pgroot/bin/pg_ctl.exe" -D "$work/data" -l "$work/server.log" -o "-p 55438" start
finish() { "$pgroot/bin/pg_ctl.exe" -D "$work/data" -m immediate stop || true; }
trap finish EXIT
"$pgroot/bin/createdb.exe" -p 55438 postgis_probe
"$pgroot/bin/psql.exe" -X -v ON_ERROR_STOP=1 -p 55438 -d postgis_probe -c 'CREATE EXTENSION postgis' -c 'SELECT postgis_full_version()'
