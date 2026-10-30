#!/usr/bin/env bash
set -euo pipefail

os=$1 workspace=$3
source_dir="$workspace/sources/address_standardizer"
pg_prefix="$workspace/postgresql"
pg_config="$pg_prefix/bin/pg_config"
dependencies="$workspace/build/dependencies"
stage="$workspace/build/stage"
payload="$workspace/payload"

if [[ $os == macos ]]; then
  jobs=$(sysctl -n hw.ncpu)
else
  jobs=$(nproc)
fi
link_flags="-L$dependencies/lib${PG_LDFLAGS:+ $PG_LDFLAGS}"

(
  cd "$workspace/sources/pcre2"
  ./configure --prefix="$dependencies" --disable-shared --enable-static --with-pic \
    --disable-pcre2-16 --disable-pcre2-32 --enable-jit
  make -j "$jobs"
  make install
)

if [[ $os == macos ]]; then
  pcre_symbols="$workspace/build/pcre2-unexported-symbols.txt"
  nm -gU "$dependencies/lib/libpcre2-8.a" | awk '$NF ~ /^_/ { print $NF }' > "$pcre_symbols"
  [[ -s $pcre_symbols ]] || { echo 'No PCRE2 symbols found in static library' >&2; exit 1; }
  link_flags+=" -Wl,-headerpad_max_install_names -Wl,-unexported_symbols_list,$pcre_symbols"
else
  link_flags+=" -Wl,--exclude-libs,libpcre2-8.a"
fi

sql_version=$(sed -n "s/^default_version = '\([^']*\)'/\1/p" "$source_dir/address_standardizer.control")
flags="-I$dependencies/include -DAS_VERSION=\\\"$sql_version\\\" -DPCRE_VERSION=2"
make -C "$source_dir" PG_CONFIG="$pg_config" PG_CPPFLAGS="$flags" PG_LDFLAGS="$link_flags" -j "$jobs"
make -C "$source_dir" PG_CONFIG="$pg_config" PG_CPPFLAGS="$flags" PG_LDFLAGS="$link_flags" DESTDIR="$stage" install

pkglibdir=$("$pg_config" --pkglibdir)
sharedir=$("$pg_config" --sharedir)
lib_rel=${pkglibdir#"$pg_prefix"/}
share_rel=${sharedir#"$pg_prefix"/}
mkdir -p "$payload/$lib_rel" "$payload/$share_rel/extension"
find "$stage$pkglibdir" -maxdepth 1 -type f \
  \( -name 'address_standardizer.so' -o -name 'address_standardizer.dylib' \) \
  -exec cp {} "$payload/$lib_rel/" \;
cp "$stage$sharedir"/extension/address_standardizer*.control "$payload/$share_rel/extension/"
cp "$stage$sharedir"/extension/address_standardizer*.sql "$payload/$share_rel/extension/"
