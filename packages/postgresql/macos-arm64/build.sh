#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 6 ]]; then
  echo "usage: $0 SOURCE_URL SOURCE_SHA256 VERSION DEPENDENCY_PREFIX BUILD_DIR INSTALL_PREFIX" >&2
  exit 2
fi
source_url=$1
source_sha=$2
version=$3
dependency_prefix=$4
build_dir=$5
install_prefix=$6

[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo 'This recipe requires macOS ARM64' >&2; exit 1; }
[[ "$source_sha" =~ ^[0-9a-f]{64}$ ]] || { echo 'SOURCE_SHA256 must be 64 lowercase hex digits' >&2; exit 2; }
[[ "$version" =~ ^[0-9]+\.[0-9]+$ ]] || { echo 'VERSION must be a PostgreSQL minor release' >&2; exit 2; }
: "${MACOSX_DEPLOYMENT_TARGET:?Set the selected minimum macOS version}"
[[ -d "$dependency_prefix/lib" && -d "$dependency_prefix/include" ]] || { echo "Missing dependency prefix: $dependency_prefix" >&2; exit 1; }
[[ "$install_prefix" == /* ]] || { echo 'INSTALL_PREFIX must be absolute' >&2; exit 2; }

dependency_prefix=$(cd "$dependency_prefix" && pwd)
mkdir -p "$build_dir" "$install_prefix"
build_dir=$(cd "$build_dir" && pwd)
install_prefix=$(cd "$install_prefix" && pwd)
archive="$build_dir/postgresql-$version.tar.gz"

if [[ ! -f "$archive" ]]; then
  curl --fail --location --silent --show-error "$source_url" --output "$archive"
fi
actual_sha=$(shasum -a 256 "$archive" | awk '{print $1}')
[[ "$actual_sha" == "$source_sha" ]] || { echo 'PostgreSQL source checksum mismatch' >&2; exit 1; }

source_dir="$build_dir/postgresql-$version"
if [[ ! -d "$source_dir" ]]; then
  tar -xzf "$archive" -C "$build_dir"
fi

export PKG_CONFIG_PATH="$dependency_prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export CPPFLAGS="-I$dependency_prefix/include${CPPFLAGS:+ $CPPFLAGS}"
export LDFLAGS="-Wl,-headerpad_max_install_names -L$dependency_prefix/lib${LDFLAGS:+ $LDFLAGS}"
export DYLD_LIBRARY_PATH="$dependency_prefix/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"

cd "$source_dir"
./configure \
  --prefix="$install_prefix" \
  --with-icu --with-lz4 --with-zstd --with-zlib --with-ssl=openssl \
  --with-libxml --with-libxslt --with-uuid=e2fs \
  --without-readline --without-libcurl --without-gssapi --without-ldap \
  --without-pam --without-bonjour --without-libnuma --without-liburing \
  --without-selinux --without-perl --without-python --without-tcl
make -j "$(sysctl -n hw.ncpu)"
make -C contrib -j "$(sysctl -n hw.ncpu)"
make install
make -C contrib install
"$install_prefix/bin/pg_config" --version
