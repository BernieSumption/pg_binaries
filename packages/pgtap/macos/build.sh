#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 1 ]] || { echo "usage: $0 ARCH [recipe arguments]" >&2; exit 2; }
arch=$1
shift
target="macos-$arch"
export PG_BINARIES_TARGET="$target"

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
[[ $(uname -s) == Darwin && ( $(uname -m) == "$arch" || ( "$arch" == arm64 && $(uname -m) == aarch64 ) ) ]] || { echo "This recipe requires $target" >&2; exit 1; }
: "${MACOSX_DEPLOYMENT_TARGET:?Set the selected minimum macOS version}"

pg_prefix=$(cd "$pg_prefix" && pwd)
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/pgtap.XXXXXX")
trap 'rm -rf "$work"' EXIT

source_archive="$work/pgtap-$version.tar.gz"
bash "$(dirname "${BASH_SOURCE[0]}")/../../shared/fetch.sh" "$source_url" "$source_sha" "$source_archive"

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
pg_version=$("$pg_config" --version | sed 's/^PostgreSQL //')
archive="pgtap-postgresql-$pg_version-$target.tar.gz"
bash "$(dirname "${BASH_SOURCE[0]}")/../../shared/archive.sh" "$work/payload" "$output_dir/$archive"
