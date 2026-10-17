#!/usr/bin/env bash
set -euo pipefail

architecture=${1:?usage: macos-build-and-probe.sh arm64|x86_64 OUTPUT_DIRECTORY}
output=${2:?usage: macos-build-and-probe.sh arm64|x86_64 OUTPUT_DIRECTORY}
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
case "$architecture" in arm64|x86_64) ;; *) echo "unsupported architecture: $architecture" >&2; exit 2 ;; esac
mkdir -p "$output"
output=$(cd "$output" && pwd)
work=${RUNNER_TEMP:-${TMPDIR:-/tmp}}/address-standardizer-macos-"$architecture"
prefix="$work/install"
source="$work/source"
mkdir -p "$source" "$work/socket"

pg_version=18.6
extension_version=3.7.0
pcre2_version=10.48
pcre2_sha256=b6c68fdf6f3ac31388b50aa89ff0fc49c00c987c16e7b5146491d12003f2c8ed
deployment_target=11.0
export MACOSX_DEPLOYMENT_TARGET=$deployment_target
export PATH="$prefix/bin:$PATH"

cd "$source"
curl -fL --retry 3 -o "postgresql-$pg_version.tar.gz" \
  "https://ftp.postgresql.org/pub/source/v$pg_version/postgresql-$pg_version.tar.gz"
curl -fL --retry 3 -o "postgresql-$pg_version.tar.gz.sha256" \
  "https://ftp.postgresql.org/pub/source/v$pg_version/postgresql-$pg_version.tar.gz.sha256"
pg_sha=$(awk -v name="postgresql-$pg_version.tar.gz" '$2 == name {print $1}' "postgresql-$pg_version.tar.gz.sha256")
test -n "$pg_sha"
printf '%s  %s\n' "$pg_sha" "postgresql-$pg_version.tar.gz" | shasum -a 256 -c -
tar -xzf "postgresql-$pg_version.tar.gz"
cd "postgresql-$pg_version"
./configure --prefix="$prefix" --without-icu --without-readline --without-zlib
make -s -j"$(sysctl -n hw.ncpu)"
make -s install

cd "$source"
curl -fL --retry 3 -o "pcre2-$pcre2_version.tar.bz2" \
  "https://github.com/PCRE2Project/pcre2/releases/download/pcre2-$pcre2_version/pcre2-$pcre2_version.tar.bz2"
printf '%s  %s\n' "$pcre2_sha256" "pcre2-$pcre2_version.tar.bz2" | shasum -a 256 -c -
tar -xjf "pcre2-$pcre2_version.tar.bz2"
cd "pcre2-$pcre2_version"
./configure --prefix="$prefix" --enable-shared --disable-static \
  --disable-pcre2-16 --disable-pcre2-32 --enable-jit
make -s -j"$(sysctl -n hw.ncpu)"
make -s install

cd "$source"
git clone --depth 1 --branch "v$extension_version" \
  https://github.com/postgis/address_standardizer.git address_standardizer
cd address_standardizer
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" address_standardizer.control)" = 3.7
make -s PG_CONFIG="$prefix/bin/pg_config" \
  PG_CPPFLAGS="-I$prefix/include -DAS_VERSION=\\\"3.7\\\" -DPCRE_VERSION=2" \
  PG_LDFLAGS="-L$prefix/lib" -j"$(sysctl -n hw.ncpu)"
make -s PG_CONFIG="$prefix/bin/pg_config" \
  PG_CPPFLAGS="-I$prefix/include -DAS_VERSION=\\\"3.7\\\" -DPCRE_VERSION=2" \
  PG_LDFLAGS="-L$prefix/lib" install
git rev-parse HEAD > "$output/address-standardizer-commit.txt"

"$prefix/bin/initdb" -D "$work/data" --encoding=UTF8 --locale=C --no-instructions
"$prefix/bin/pg_ctl" -D "$work/data" -o "-k $work/socket -p 55432 -h ''" -w start
stop_server() { "$prefix/bin/pg_ctl" -D "$work/data" -m immediate stop >/dev/null 2>&1 || true; }
trap stop_server EXIT
"$prefix/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 \
  -d postgres -f "$script_dir/probe.sql" | tee "$output/probe-output.txt"
"$prefix/bin/pg_ctl" -D "$work/data" -m fast -w stop
trap - EXIT

extension_dylib=$(find "$prefix/lib/postgresql" -maxdepth 1 -name 'address_standardizer.*' -print -quit)
pcre2_dylib=$(find "$prefix/lib" -maxdepth 1 -name 'libpcre2-8*.dylib' -print -quit)
test -f "$extension_dylib"
test -n "$pcre2_dylib"
{
  echo "architecture=$architecture"
  echo "macos_version=$(sw_vers -productVersion)"
  echo "deployment_target=$deployment_target"
  echo "postgresql_version=$pg_version"
  echo "address_standardizer_version=$extension_version"
  echo "pcre2_version=$pcre2_version"
  for dylib in "$extension_dylib" "$pcre2_dylib"; do
    echo "--- $dylib"
    lipo -archs "$dylib"
    otool -l "$dylib" | awk '
      /cmd LC_BUILD_VERSION/ {build=1; next}
      build && /minos / {print "minos " $2; build=0}
      /cmd LC_VERSION_MIN_MACOSX/ {legacy=1; next}
      legacy && /version / {print "minos " $2; legacy=0}
    '
    otool -L "$dylib"
  done
} | tee "$output/macho-inspection.txt"

for dylib in "$extension_dylib" "$pcre2_dylib"; do
  lipo -archs "$dylib" | grep -Eq "(^| )$architecture( |$)"
  minimum=$(otool -l "$dylib" | awk '/cmd LC_BUILD_VERSION/ {build=1; next} build && /minos / {print $2; exit} /cmd LC_VERSION_MIN_MACOSX/ {legacy=1; next} legacy && /version / {print $2; exit}')
  test -n "$minimum"
  awk -v version="$minimum" 'BEGIN {split(version,a,"."); if (a[1] > 11 || (a[1] == 11 && a[2] > 0)) exit 1}'
done
for dylib in "$extension_dylib" "$pcre2_dylib"; do
  if otool -L "$dylib" | grep -E '/opt/homebrew/|/usr/local/opt/'; then
    echo "Probe dylib links to a Homebrew dependency: $dylib" >&2
    exit 1
  fi
done
