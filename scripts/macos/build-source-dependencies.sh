#!/usr/bin/env bash
set -euo pipefail

architecture=${1:?usage: build-source-dependencies.sh <arm64|x86_64> <prefix>}
prefix_arg=${2:?usage: build-source-dependencies.sh <arm64|x86_64> <prefix>}
case "$architecture" in
  arm64|x86_64) ;;
  *) echo "Unsupported macOS architecture: $architecture" >&2; exit 2 ;;
esac
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This builder requires native macOS $architecture" >&2
  exit 1
fi

prefix=$(mkdir -p "$prefix_arg" && cd "$prefix_arg" && pwd)
work_dir=$(mktemp -d "${RUNNER_TEMP:-/tmp}/pg-macos-dependencies.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
export MACOSX_DEPLOYMENT_TARGET=11.0
jobs=$(sysctl -n hw.ncpu)

fetch_source() {
  local name=$1 url=$2 expected=$3 archive="$work_dir/$1"
  curl --fail --location --retry 3 "$url" --output "$archive"
  local actual
  actual=$(shasum -a 256 "$archive" | awk '{print $1}')
  if [[ $actual != "$expected" ]]; then
    echo "$name SHA-256 mismatch: expected $expected, got $actual" >&2
    return 1
  fi
  printf '%s  %s\n' "$actual" "$name" >&2
  printf '%s\n' "$archive"
}

unpack() {
  local archive=$1 destination=$2 format=$3
  mkdir -p "$destination"
  case "$format" in
    gz) tar -xzf "$archive" -C "$destination" --strip-components=1 ;;
    xz) tar -xJf "$archive" -C "$destination" --strip-components=1 ;;
    *) echo "Unsupported source archive format: $format" >&2; return 2 ;;
  esac
}

build_log="$work_dir/build.log"
run_build() {
  local label=$1
  shift
  local started=$SECONDS
  echo "Starting $label build" >&2
  : > "$build_log"
  if "$@" > "$build_log" 2>&1; then
    grep -E '(^| )clang|\.dylib|install|error:|warning:' "$build_log" | tail -n 30 || true
    echo "Completed $label build in $((SECONDS - started))s" >&2
  else
    echo "$label build failed; final build output:" >&2
    tail -n 100 "$build_log" >&2
    return 1
  fi
}

snapshot_dylibs() {
  find "$prefix" -name '*.dylib' -print | sort
}

check_installed_libraries() {
  local package=$1 before=$2 libraries
  libraries=$(comm -13 "$before" <(snapshot_dylibs) | awk -F/ '{print $NF}' | sort -u | paste -sd, -)
  if [[ -z $libraries ]]; then
    echo "$package installed no dylibs in $prefix" >&2
    return 1
  fi
}

openssl_archive=$(fetch_source openssl-3.5.8.tar.gz \
  https://github.com/openssl/openssl/releases/download/openssl-3.5.8/openssl-3.5.8.tar.gz \
  a8f84a39918ec6415ce765d9b429d313ba97b8143169c172e734b9514464f5b2)
openssl_before="$work_dir/openssl-before.txt"
snapshot_dylibs > "$openssl_before"
unpack "$openssl_archive" "$work_dir/openssl" gz
case "$architecture" in
  arm64) openssl_target=darwin64-arm64-cc ;;
  x86_64) openssl_target=darwin64-x86_64-cc ;;
esac
run_build OpenSSL bash -c 'cd "$1" && ./Configure "$2" shared no-tests --prefix="$3" --openssldir="$3/ssl" --libdir=lib && make -j"$4" && make install_sw' _ \
  "$work_dir/openssl" "$openssl_target" "$prefix" "$jobs"
check_installed_libraries openssl "$openssl_before"

icu_archive=$(fetch_source icu4c-78.3-sources.tgz \
  https://github.com/unicode-org/icu/releases/download/release-78.3/icu4c-78.3-sources.tgz \
  3a2e7a47604ba702f345878308e6fefeca612ee895cf4a5f222e7955fabfe0c0)
icu_before="$work_dir/icu-before.txt"
snapshot_dylibs > "$icu_before"
unpack "$icu_archive" "$work_dir/icu" gz
icu_configure=$(find "$work_dir/icu" -type f -path '*/source/configure' -print -quit)
if [[ -z $icu_configure ]]; then
  echo "ICU source/configure was not present in the pinned source archive" >&2
  exit 1
fi
run_build ICU bash -c 'cd "${1%/configure}" && ./configure --prefix="$2" --enable-shared --disable-static --disable-samples --disable-tests && make -j"$3" && make install' _ \
  "$icu_configure" "$prefix" "$jobs"
check_installed_libraries icu4c "$icu_before"

lz4_archive=$(fetch_source lz4-1.10.0.tar.gz \
  https://github.com/lz4/lz4/releases/download/v1.10.0/lz4-1.10.0.tar.gz \
  537512904744b35e232912055ccf8ec66d768639ff3abe5788d90d792ec5f48b)
lz4_before="$work_dir/lz4-before.txt"
snapshot_dylibs > "$lz4_before"
unpack "$lz4_archive" "$work_dir/lz4" gz
run_build LZ4 bash -c 'cd "$1" && make -j"$3" CC=clang && make install PREFIX="$2" CC=clang' _ \
  "$work_dir/lz4" "$prefix" "$jobs"
check_installed_libraries lz4 "$lz4_before"

zstd_archive=$(fetch_source zstd-1.5.7.tar.gz \
  https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz \
  eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3)
zstd_before="$work_dir/zstd-before.txt"
snapshot_dylibs > "$zstd_before"
unpack "$zstd_archive" "$work_dir/zstd" gz
run_build Zstandard bash -c 'cd "$1" && make -j"$3" CC=clang && make install PREFIX="$2" CC=clang' _ \
  "$work_dir/zstd" "$prefix" "$jobs"
check_installed_libraries zstd "$zstd_before"

xml_archive=$(fetch_source libxml2-2.15.4.tar.xz \
  https://download.gnome.org/sources/libxml2/2.15/libxml2-2.15.4.tar.xz \
  98087fd181d9070724f3fbc65c7377db03038eb92bd882374daff44940138821)
xml_before="$work_dir/libxml2-before.txt"
snapshot_dylibs > "$xml_before"
unpack "$xml_archive" "$work_dir/libxml2" xz
run_build libxml2 bash -c 'cd "$1" && ./configure --prefix="$2" --with-iconv --without-zlib --without-lzma --without-icu --without-python --without-readline --without-history --without-docs && make -j"$3" && make install' _ \
  "$work_dir/libxml2" "$prefix" "$jobs"
check_installed_libraries libxml2 "$xml_before"

xslt_archive=$(fetch_source libxslt-1.1.45.tar.xz \
  https://download.gnome.org/sources/libxslt/1.1/libxslt-1.1.45.tar.xz \
  9acfe68419c4d06a45c550321b3212762d92f41465062ca4ea19e632ee5d216e)
xslt_before="$work_dir/libxslt-before.txt"
snapshot_dylibs > "$xslt_before"
unpack "$xslt_archive" "$work_dir/libxslt" xz
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export CPPFLAGS="-I$prefix/include${CPPFLAGS:+ $CPPFLAGS}"
export LDFLAGS="-L$prefix/lib${LDFLAGS:+ $LDFLAGS}"
run_build libxslt bash -c 'cd "$1" && ./configure --prefix="$2" --without-python --without-crypto --without-plugins && make -j"$3" && make install' _ \
  "$work_dir/libxslt" "$prefix" "$jobs"

check_installed_libraries libxslt "$xslt_before"
