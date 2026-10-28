#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 1 ]]; then
  echo "usage: $0 TOOL_PREFIX" >&2
  exit 2
fi

prefix=$1
mkdir -p "$prefix"
prefix=$(cd "$prefix" && pwd)
version=2.5.1
url="https://distfiles.ariadne.space/pkgconf/pkgconf-$version.tar.gz"
sha256=ab89d59810d9cad5dfcd508f25efab8ea0b1c8e7bad91c2b6351f13e6a5940d8
work=$(mktemp -d "${TMPDIR:-/tmp}/pg-pkgconf.XXXXXX")
trap 'rm -rf "$work"' EXIT

curl --fail --location --retry 3 --silent --show-error "$url" --output "$work/pkgconf.tar.gz"
actual=$(shasum -a 256 "$work/pkgconf.tar.gz" | awk '{print $1}')
[[ "$actual" == "$sha256" ]] || { echo 'pkgconf source checksum mismatch' >&2; exit 1; }
tar -xzf "$work/pkgconf.tar.gz" -C "$work"
cd "$work/pkgconf-$version"
./configure --prefix="$prefix"
make -j "$(sysctl -n hw.ncpu)"
make install
ln -sf pkgconf "$prefix/bin/pkg-config"
"$prefix/bin/pkg-config" --version
