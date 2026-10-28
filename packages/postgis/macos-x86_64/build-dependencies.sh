#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 1 ]]; then
  echo "usage: $0 DEPENDENCY_PREFIX" >&2
  exit 2
fi
[[ $(uname -s) == Darwin && $(uname -m) == x86_64 ]] || { echo 'This recipe requires macOS x86_64' >&2; exit 1; }
: "${MACOSX_DEPLOYMENT_TARGET:?Set the selected minimum macOS version}"

prefix=$1
mkdir -p "$prefix"
prefix=$(cd "$prefix" && pwd)
recipe_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$recipe_dir/../../.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/postgis-dependencies.XXXXXX")
trap 'rm -rf "$work"' EXIT

read -r micromamba_version micromamba_sha lock_sha sfcgal_version sfcgal_commit sfcgal_url sfcgal_sha < <(
  python3 - "$repo_root/support.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    selected = json.load(source)["packages"]["postgis"]["build_inputs"]["macos-x86_64"]
sfcgal = selected["sfcgal"]
print(selected["micromamba"], selected["micromamba_sha256"], selected["conda_lock_sha256"],
      sfcgal["version"], sfcgal["commit"], sfcgal["url"], sfcgal["sha256"])
PY
)
actual=$(shasum -a 256 "$recipe_dir/conda-lock.txt" | awk '{print $1}')
[[ "$actual" == "$lock_sha" ]] || { echo 'PostGIS conda lock checksum mismatch' >&2; exit 1; }
micromamba_url="https://micro.mamba.pm/api/micromamba/osx-64/$micromamba_version"
curl --fail --location --retry 3 --silent --show-error "$micromamba_url" --output "$work/micromamba.tar.bz2"
actual=$(shasum -a 256 "$work/micromamba.tar.bz2" | awk '{print $1}')
[[ "$actual" == "$micromamba_sha" ]] || { echo 'micromamba archive checksum mismatch' >&2; exit 1; }
tar -xjf "$work/micromamba.tar.bz2" -C "$work" bin/micromamba
export MAMBA_ROOT_PREFIX="$work/mamba-root"
"$work/bin/micromamba" create --yes --prefix "$prefix" --file "$recipe_dir/conda-lock.txt"

curl --fail --location --retry 3 --silent --show-error "$sfcgal_url" --output "$work/sfcgal.tar.gz"
actual=$(shasum -a 256 "$work/sfcgal.tar.gz" | awk '{print $1}')
[[ "$actual" == "$sfcgal_sha" ]] || { echo 'SFCGAL source checksum mismatch' >&2; exit 1; }
tar -xzf "$work/sfcgal.tar.gz" -C "$work"
"$prefix/bin/cmake" -S "$work/SFCGAL-$sfcgal_commit" -B "$work/sfcgal-build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_PREFIX_PATH="$prefix" \
  -DCMAKE_INSTALL_RPATH="$prefix/lib" -DCMAKE_OSX_DEPLOYMENT_TARGET="$MACOSX_DEPLOYMENT_TARGET" \
  -DSFCGAL_BUILD_TESTS=OFF
"$prefix/bin/cmake" --build "$work/sfcgal-build" --parallel "$(sysctl -n hw.ncpu)"
"$prefix/bin/cmake" --install "$work/sfcgal-build"
[[ $("$prefix/bin/sfcgal-config" --version) == "$sfcgal_version" ]] || { echo 'SFCGAL installed version mismatch' >&2; exit 1; }
