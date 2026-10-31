#!/usr/bin/env bash
set -euo pipefail

os=$1 arch=$2 workspace=$3
internal=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work="$workspace/build"
prefix="$work/dependencies"
micromamba_version=2.10.0
if [[ $arch == arm64 ]]; then
  subdir=osx-arm64
  micromamba_sha=acef4eaab19ec2174ad5a449e5aad981ca326270db819502ff096a92fc31caa6
else
  subdir=osx-64
  micromamba_sha=17b20c4271d65c030a5c86788f5ca86eb575187209f626edabdb8c6a875c6838
fi
curl --fail --location --retry 3 --silent --show-error \
  "https://micro.mamba.pm/api/micromamba/$subdir/$micromamba_version" --output "$work/micromamba.tar.bz2"
actual=$(shasum -a 256 "$work/micromamba.tar.bz2" | awk '{print $1}')
[[ $actual == "$micromamba_sha" ]] || { echo 'micromamba archive checksum mismatch' >&2; exit 1; }
tar -xjf "$work/micromamba.tar.bz2" -C "$work" bin/micromamba
export MAMBA_ROOT_PREFIX="$work/mamba-root"
"$work/bin/micromamba" create --yes --prefix "$prefix" --file "$internal/macos-$arch/conda-lock.txt"

# Keep SFCGAL with the locked shared geospatial libraries. Converting the full
# dependency stack to static builds would also require preserving GDAL's drivers.
"$prefix/bin/cmake" -S "$workspace/sources/sfcgal" -B "$work/sfcgal-build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_PREFIX_PATH="$prefix" \
  -DCMAKE_INSTALL_RPATH="$prefix/lib" -DCMAKE_OSX_DEPLOYMENT_TARGET="$MACOSX_DEPLOYMENT_TARGET" \
  -DSFCGAL_BUILD_TESTS=OFF
"$prefix/bin/cmake" --build "$work/sfcgal-build" --parallel "$(sysctl -n hw.ncpu)"
"$prefix/bin/cmake" --install "$work/sfcgal-build"
