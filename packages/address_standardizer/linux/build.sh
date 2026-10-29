#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 1 ]] || { echo "usage: $0 ARCH [recipe arguments]" >&2; exit 2; }
arch=$1
shift
target="linux-$arch"
export PG_BINARIES_TARGET="$target"
[[ $# == 5 ]] || { echo "usage: $0 SOURCE_URL SOURCE_SHA256 VERSION POSTGRESQL_PREFIX OUTPUT_DIR" >&2; exit 2; }
source_url=$1 source_sha=$2 version=$3 pg_prefix=$4 output_dir=$5
[[ $source_sha =~ ^[0-9a-f]{64}$ && $version == 3.7.0 ]] || { echo 'Invalid source checksum or version' >&2; exit 2; }
[[ $(uname -s) == Linux && ( $(uname -m) == "$arch" || ( "$arch" == arm64 && $(uname -m) == aarch64 ) ) ]] || { echo "This recipe requires $target" >&2; exit 1; }
[[ -x $pg_prefix/bin/pg_config ]] || { echo "Missing pg_config under $pg_prefix" >&2; exit 1; }
pg_prefix=$(cd "$pg_prefix" && pwd); repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
mkdir -p "$output_dir"; output_dir=$(cd "$output_dir" && pwd); work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
read -r pcre_version pcre_url pcre_sha < <(python3 - "$repo/support.json" <<'PY'
import json,os,sys
s=json.load(open(sys.argv[1]))['packages']['address_standardizer']['build_inputs'][os.environ['PG_BINARIES_TARGET']]['pcre2']
print(s['version'],s['url'],s['sha256'])
PY
)
bash "$(dirname "${BASH_SOURCE[0]}")/../../shared/fetch.sh" "$source_url" "$source_sha" "$work/source.tar.gz"
[[ $(tar -tzf "$work/source.tar.gz" | sed -n '1s,/.*,,p') == "address_standardizer-$version" ]]
tar -xzf "$work/source.tar.gz" -C "$work"; src="$work/address_standardizer-$version"
for c in address_standardizer.control address_standardizer_data_us.control; do [[ $(sed -n "s/^default_version = '\([^']*\)'/\1/p" "$src/$c") == 3.7 ]]; done
bash "$(dirname "${BASH_SOURCE[0]}")/../../shared/fetch.sh" "$pcre_url" "$pcre_sha" "$work/pcre2.tar.bz2"
tar -xjf "$work/pcre2.tar.bz2" -C "$work"; pcre_src="$work/pcre2-$pcre_version"; pcre_prefix="$work/pcre-prefix"
(cd "$pcre_src" && ./configure --prefix="$pcre_prefix" --enable-shared --disable-static --disable-pcre2-16 --disable-pcre2-32 --enable-jit && make -j "$(nproc)" && make install)
pg_config="$pg_prefix/bin/pg_config"; flags="-I$pcre_prefix/include -DAS_VERSION=\\\"3.7\\\" -DPCRE_VERSION=2"
make -C "$src" PG_CONFIG="$pg_config" PG_CPPFLAGS="$flags" PG_LDFLAGS="-L$pcre_prefix/lib -Wl,-rpath,\$ORIGIN" -j "$(nproc)"
stage="$work/stage"; make -C "$src" PG_CONFIG="$pg_config" PG_CPPFLAGS="$flags" PG_LDFLAGS="-L$pcre_prefix/lib -Wl,-rpath,\$ORIGIN" DESTDIR="$stage" install
pkglibdir=$("$pg_config" --pkglibdir); sharedir=$("$pg_config" --sharedir)
case $pkglibdir in "$pg_prefix"/*) lib_rel=${pkglibdir#"$pg_prefix"/};; *) exit 1;; esac
case $sharedir in "$pg_prefix"/*) share_rel=${sharedir#"$pg_prefix"/};; *) exit 1;; esac
payload="$work/payload/postgresql"; mkdir -p "$payload/$lib_rel" "$payload/$share_rel/extension"
cp "$stage$pkglibdir/address_standardizer.so" "$payload/$lib_rel/"
for name in address_standardizer address_standardizer_data_us; do cp "$stage$sharedir"/extension/$name* "$payload/$share_rel/extension/"; done
cp -L "$pcre_prefix/lib/libpcre2-8.so."* "$payload/$lib_rel/"
patchelf --set-rpath '$ORIGIN' "$payload/$lib_rel/address_standardizer.so"
pg_version=$("$pg_config" --version | sed 's/^PostgreSQL //')
archive="address_standardizer-postgresql-$pg_version-$target.tar.gz"
bash "$(dirname "${BASH_SOURCE[0]}")/../../shared/archive.sh" "$work/payload" "$output_dir/$archive"
