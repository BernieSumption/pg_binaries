#!/usr/bin/env bash
set -euo pipefail
arch=$1 workspace=$2
prefix="$workspace/build/dependencies"
jobs=$(sysctl -n hw.ncpu)
mkdir -p "$prefix"

for name in openssl icu lz4 zstd libxml2 libxslt; do
  source_dir="$workspace/sources/$name"
  case "$name" in
    openssl)
      (cd "$source_dir" && ./Configure "darwin64-$arch-cc" shared no-tests --prefix="$prefix" --openssldir="$prefix/ssl" --libdir=lib && make -j "$jobs" && make install_sw)
      ;;
    icu)
      # ICU archives can contain source/configure below their enclosing directory.
      configure=$(find "$source_dir" -type f -name configure -path '*/source/configure' -print -quit)
      [[ -n $configure ]] || { echo 'ICU source/configure is missing' >&2; exit 1; }
      (cd "${configure%/configure}" && ./configure --prefix="$prefix" --enable-shared --disable-static --disable-samples --disable-tests && make -j "$jobs" && make install)
      ;;
    lz4|zstd)
      (cd "$source_dir" && make -j "$jobs" CC=clang && make install PREFIX="$prefix" CC=clang)
      library="$prefix/lib/lib$name.1.dylib"
      install_name_tool -id "$library" "$prefix/lib/$(readlink "$library")"
      ;;
    libxml2)
      (cd "$source_dir" && ./configure --prefix="$prefix" --with-iconv --without-zlib --without-lzma --without-icu --without-python --without-readline --without-history --without-docs && make -j "$jobs" && make install)
      ;;
    libxslt)
      export PATH="$prefix/bin:$PATH"
      export PKG_CONFIG_PATH="$prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
      export CPPFLAGS="-I$prefix/include${CPPFLAGS:+ $CPPFLAGS}"
      export LDFLAGS="-L$prefix/lib${LDFLAGS:+ $LDFLAGS}"
      (cd "$source_dir" && ./configure --prefix="$prefix" --without-python --without-crypto --without-plugins && make -j "$jobs" && make install)
      ;;
  esac
done
