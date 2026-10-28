#!/usr/bin/env bash
set -euo pipefail

[[ $# == 6 ]] || { echo "usage: $0 SOURCE_URL SOURCE_SHA256 VERSION DEPENDENCY_PREFIX BUILD_DIR INSTALL_PREFIX" >&2; exit 2; }
source_url=$1 source_sha=$2 version=$3 build_dir=$5 install_prefix=$6
[[ $source_sha =~ ^[0-9a-f]{64}$ && $version =~ ^[0-9]+(\.[0-9]+)+$ ]] || { echo 'Invalid PostgreSQL source selection' >&2; exit 2; }
[[ $(uname -s) == Linux && $(uname -m) == aarch64 ]] || { echo 'Build requires Linux ARM64' >&2; exit 1; }
mkdir -p "$build_dir" "$install_prefix"
build_dir=$(cd "$build_dir" && pwd)
install_prefix=$(cd "$install_prefix" && pwd)
curl --fail --location --retry 3 "$source_url" -o "$build_dir/postgresql.tar.gz"
printf '%s  %s\n' "$source_sha" "$build_dir/postgresql.tar.gz" | sha256sum -c -
mkdir -p "$build_dir/source"
tar -xzf "$build_dir/postgresql.tar.gz" -C "$build_dir/source"
source_dir="$build_dir/source/postgresql-$version"
[[ -d $source_dir ]] || { echo 'Selected PostgreSQL source directory is missing' >&2; exit 1; }
cd "$source_dir"
CFLAGS='-O2 -g -march=armv8-a' ./configure --prefix="$install_prefix" --disable-rpath \
  --with-icu --with-lz4 --with-zstd --with-ssl=openssl --with-libxml --with-libxslt \
  --with-zlib --with-uuid=e2fs --without-readline --without-libcurl --without-gssapi \
  --without-ldap --without-pam --without-bonjour --without-libnuma --without-liburing \
  --without-selinux --without-perl --without-python --without-tcl
make -j "$(nproc)"
make install
make -C contrib -j "$(nproc)"
make -C contrib install
