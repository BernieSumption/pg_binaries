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
[[ "$version" =~ ^[0-9]+(\.[0-9]+)+$ ]] || { echo 'VERSION must be a dotted numeric release' >&2; exit 2; }
[[ -x "$pg_prefix/bin/pg_config" ]] || { echo "Missing PostgreSQL pg_config under $pg_prefix" >&2; exit 1; }
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo 'This recipe requires macOS ARM64' >&2; exit 1; }
: "${MACOSX_DEPLOYMENT_TARGET:?Set the selected minimum macOS version}"

pg_prefix=$(cd "$pg_prefix" && pwd)
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/pgtap.XXXXXX")
trap 'rm -rf "$work"' EXIT

source_archive="$work/pgtap-$version.tar.gz"
curl --fail --location --silent --show-error "$source_url" --output "$source_archive"
actual_sha=$(shasum -a 256 "$source_archive" | awk '{print $1}')
[[ "$actual_sha" == "$source_sha" ]] || { echo 'pgTAP source checksum mismatch' >&2; exit 1; }

archive_root=$(tar -tzf "$source_archive" | sed -n '1s,/.*,,p')
[[ "$archive_root" == "pgtap-$version" ]] || { echo "Unexpected source archive root: $archive_root" >&2; exit 1; }
tar -xzf "$source_archive" -C "$work"
source_dir="$work/pgtap-$version"
pg_config="$pg_prefix/bin/pg_config"
[[ $(sed -n "s/^default_version = '\([^']*\)'/\1/p" "$source_dir/pgtap.control") == "$version" ]] || {
  echo 'pgTAP control file version does not match VERSION' >&2
  exit 1
}

make -C "$source_dir" USE_PGXS=1 PG_CONFIG="$pg_config"
stage="$work/stage"
make -C "$source_dir" USE_PGXS=1 PG_CONFIG="$pg_config" DESTDIR="$stage" install

sharedir=$("$pg_config" --sharedir)
case "$sharedir" in "$pg_prefix"/*) share_rel=${sharedir#"$pg_prefix"/} ;; *) echo "PostgreSQL share path is outside prefix: $sharedir" >&2; exit 1 ;; esac
staged_extension_dir="$stage$sharedir/extension"
[[ -s "$staged_extension_dir/pgtap.control" ]] || { echo 'pgTAP did not install pgtap.control' >&2; exit 1; }

payload="$work/payload/postgresql"
mkdir -p "$payload/$share_rel/extension"
shopt -s nullglob
extension_files=("$staged_extension_dir"/pgtap*)
[[ ${#extension_files[@]} -gt 0 ]] || { echo 'pgTAP did not install extension files' >&2; exit 1; }
cp "${extension_files[@]}" "$payload/$share_rel/extension/"
printf '%s\n' 'See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md' > "$payload/LICENCE"

pg_version=$("$pg_config" --version | sed 's/^PostgreSQL //')
archive="pgtap-postgresql-$pg_version-macos-arm64.tar.gz"
tar -C "$work/payload" -czf "$output_dir/$archive" postgresql
shasum -a 256 "$output_dir/$archive" > "$output_dir/$archive.sha256"
echo "$output_dir/$archive"
