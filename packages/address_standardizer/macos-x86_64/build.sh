#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 SOURCE_URL SOURCE_SHA256 VERSION POSTGRESQL_PREFIX OUTPUT_DIR" >&2
  exit 2
}

[[ $# == 5 ]] || usage
source_url=$1
source_sha=$2
version=$3
pg_prefix=$4
output_dir=$5

[[ "$source_sha" =~ ^[0-9a-f]{64}$ ]] || { echo 'SOURCE_SHA256 must be 64 lowercase hex digits' >&2; exit 2; }
[[ "$version" == 3.7.0 ]] || { echo 'This recipe builds Address Standardizer 3.7.0' >&2; exit 2; }
[[ -x "$pg_prefix/bin/pg_config" ]] || { echo "Missing PostgreSQL pg_config under $pg_prefix" >&2; exit 1; }
[[ $(uname -s) == Darwin && $(uname -m) == x86_64 ]] || { echo 'This recipe requires macOS x86_64' >&2; exit 1; }
: "${MACOSX_DEPLOYMENT_TARGET:?Set the selected minimum macOS version}"

pg_prefix=$(cd "$pg_prefix" && pwd)
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/address-standardizer.XXXXXX")
trap 'rm -rf "$work"' EXIT
pg_config="$pg_prefix/bin/pg_config"
selection=$(python3 - "$repo/support.json" <<'PY'
import json
import sys
from pathlib import Path

support = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
source = support["packages"]["address_standardizer"]["build_inputs"]["macos-x86_64"]["pcre2"]
print(source["version"], source["url"], source["sha256"])
PY
)
read -r pcre_version pcre_url pcre_sha <<< "$selection"

curl --fail --location --silent --show-error "$source_url" --output "$work/address_standardizer-$version.tar.gz"
actual_sha=$(shasum -a 256 "$work/address_standardizer-$version.tar.gz" | awk '{print $1}')
[[ "$actual_sha" == "$source_sha" ]] || { echo 'Address Standardizer source checksum mismatch' >&2; exit 1; }
archive_root=$(tar -tzf "$work/address_standardizer-$version.tar.gz" | sed -n '1s,/.*,,p')
[[ "$archive_root" == "address_standardizer-$version" ]] || { echo "Unexpected source archive root: $archive_root" >&2; exit 1; }
tar -xzf "$work/address_standardizer-$version.tar.gz" -C "$work"
source_dir="$work/address_standardizer-$version"
for control in address_standardizer.control address_standardizer_data_us.control; do
  [[ $(sed -n "s/^default_version = '\([^']*\)'/\1/p" "$source_dir/$control") == 3.7 ]] || {
    echo "Unexpected default_version in $control (expected 3.7)" >&2; exit 1;
  }
done

curl --fail --location --silent --show-error "$pcre_url" --output "$work/pcre2-$pcre_version.tar.bz2"
actual_sha=$(shasum -a 256 "$work/pcre2-$pcre_version.tar.bz2" | awk '{print $1}')
[[ "$actual_sha" == "$pcre_sha" ]] || { echo 'PCRE2 source checksum mismatch' >&2; exit 1; }
tar -xjf "$work/pcre2-$pcre_version.tar.bz2" -C "$work"
pcre_source="$work/pcre2-$pcre_version"
pcre_prefix="$work/pcre2-prefix"
(cd "$pcre_source" && ./configure --prefix="$pcre_prefix" --enable-shared --disable-static --disable-pcre2-16 --disable-pcre2-32 --enable-jit && make -j "$(sysctl -n hw.ncpu)" && make install)

build_flags=(-I"$pcre_prefix/include" '-DAS_VERSION=\"3.7\"' -DPCRE_VERSION=2)
make -C "$source_dir" PG_CONFIG="$pg_config" PG_CPPFLAGS="${build_flags[*]}" PG_LDFLAGS="-L$pcre_prefix/lib" -j "$(sysctl -n hw.ncpu)"
stage="$work/stage"
make -C "$source_dir" PG_CONFIG="$pg_config" PG_CPPFLAGS="${build_flags[*]}" PG_LDFLAGS="-L$pcre_prefix/lib" DESTDIR="$stage" install

pkglibdir=$("$pg_config" --pkglibdir)
sharedir=$("$pg_config" --sharedir)
case "$pkglibdir" in "$pg_prefix"/*) lib_rel=${pkglibdir#"$pg_prefix"/} ;; *) echo "PostgreSQL library path is outside prefix: $pkglibdir" >&2; exit 1 ;; esac
case "$sharedir" in "$pg_prefix"/*) share_rel=${sharedir#"$pg_prefix"/} ;; *) echo "PostgreSQL share path is outside prefix: $sharedir" >&2; exit 1 ;; esac
stage_root="$stage$pg_prefix"
payload="$work/payload/postgresql"
mkdir -p "$payload/$lib_rel" "$payload/$share_rel/extension"
for module in address_standardizer.dylib address_standardizer.so; do
  if [[ -s "$stage_root/$lib_rel/$module" ]]; then cp "$stage_root/$lib_rel/$module" "$payload/$lib_rel/"; break; fi
done
[[ -s "$payload/$lib_rel/address_standardizer.dylib" || -s "$payload/$lib_rel/address_standardizer.so" ]] || {
  echo 'Address Standardizer module was not installed' >&2; exit 1;
}
for name in address_standardizer address_standardizer_data_us; do
  for file in "$stage_root/$share_rel/extension/$name"*; do
    [[ -f "$file" ]] && cp "$file" "$payload/$share_rel/extension/"
  done
done
for control in address_standardizer.control address_standardizer_data_us.control; do
  [[ -s "$payload/$share_rel/extension/$control" ]] || { echo "Missing installed $control" >&2; exit 1; }
done

python3 "$repo/platforms/macos/bundle.py" "$payload" "$pcre_prefix"
printf '%s\n' 'See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md' > "$payload/LICENCE"
pg_version=$("$pg_config" --version | sed 's/^PostgreSQL //')
archive="address_standardizer-postgresql-$pg_version-macos-x86_64.tar.gz"
tar -C "$work/payload" -czf "$output_dir/$archive" postgresql
shasum -a 256 "$output_dir/$archive" > "$output_dir/$archive.sha256"
echo "$output_dir/$archive"
