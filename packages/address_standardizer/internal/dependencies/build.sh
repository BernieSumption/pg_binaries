#!/usr/bin/env bash
set -euo pipefail

os=$1 workspace=$3
dependencies="$workspace/build/dependencies"

if [[ $os == macos ]]; then
  jobs=$(sysctl -n hw.ncpu)
else
  jobs=$(nproc)
fi

(
  cd "$workspace/sources/pcre2"
  ./configure --prefix="$dependencies" --disable-shared --enable-static --with-pic \
    --disable-pcre2-16 --disable-pcre2-32 --enable-jit
  make -j "$jobs"
  make install
)
