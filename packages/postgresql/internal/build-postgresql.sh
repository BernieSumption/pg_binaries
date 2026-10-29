#!/usr/bin/env bash
set -euo pipefail
os=$1 arch=$2 workspace=$3
source_dir="$workspace/sources/postgresql"
install_prefix="$workspace/postgresql"
dependency_prefix="$workspace/build/dependencies"
mkdir -p "$install_prefix" "$workspace/build/postgresql"
configure_options=("--prefix=$install_prefix")

if [[ $os == macos ]]; then
  bash "$(dirname "${BASH_SOURCE[0]}")/build-macos-dependencies.sh" "$arch" "$workspace"
  export PKG_CONFIG_PATH="$dependency_prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
  export CPPFLAGS="-I$dependency_prefix/include${CPPFLAGS:+ $CPPFLAGS}"
  export LDFLAGS="-Wl,-headerpad_max_install_names -L$dependency_prefix/lib${LDFLAGS:+ $LDFLAGS}"
  export DYLD_LIBRARY_PATH="$dependency_prefix/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
  jobs=$(sysctl -n hw.ncpu)
else
  jobs=$(nproc)
  if [[ $arch == arm64 ]]; then machine=armv8-a; else machine=x86-64; fi
  export CFLAGS="-O2 -g -march=$machine"
  configure_options+=(--disable-rpath)
fi

cd "$workspace/build/postgresql"
"$source_dir/configure" "${configure_options[@]}" \
  --with-icu --with-lz4 --with-zstd --with-zlib --with-ssl=openssl \
  --with-libxml --with-libxslt --with-uuid=e2fs \
  --without-readline --without-libcurl --without-gssapi --without-ldap \
  --without-pam --without-bonjour --without-libnuma --without-liburing \
  --without-selinux --without-perl --without-python --without-tcl
make -j "$jobs"
make -C contrib -j "$jobs"
make install
make -C contrib install
