#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 1 ]] || { echo "usage: $0 ARCH [recipe arguments]" >&2; exit 2; }
arch=$1
shift
target="linux-$arch"
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
[[ $(uname -s) == Linux && ( $(uname -m) == "$arch" || ( "$arch" == arm64 && $(uname -m) == aarch64 ) ) ]] || { echo "This recipe requires $target" >&2; exit 1; }

pg_prefix=$(cd "$pg_prefix" && pwd)
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/collection.XXXXXX")
trap 'rm -rf "$work"' EXIT

source_archive="$work/pgcollection-v$version.tar.gz"
bash "$(dirname "${BASH_SOURCE[0]}")/../../shared/fetch.sh" "$source_url" "$source_sha" "$source_archive"

archive_root=$(tar -tzf "$source_archive" | sed -n '1s,/.*,,p')
[[ "$archive_root" == "pgcollection-$version" ]] || { echo "Unexpected source archive root: $archive_root" >&2; exit 1; }
tar -xzf "$source_archive" -C "$work"
source_dir="$work/pgcollection-$version"
pg_config="$pg_prefix/bin/pg_config"
[[ -f "$source_dir/collection.control.in" || -f "$source_dir/collection.control" ]] || {
  echo 'pgcollection source does not define the collection SQL extension' >&2; exit 1;
}
[[ $(sed -n 's/^EXTVERSION = //p' "$source_dir/Makefile") == "$version" ]] || {
  echo 'pgcollection Makefile version does not match VERSION' >&2; exit 1;
}

make -C "$source_dir" PG_CONFIG="$pg_config"  -j "$(nproc)"
stage="$work/stage"
make -C "$source_dir" PG_CONFIG="$pg_config" DESTDIR="$stage" install

pkglibdir=$("$pg_config" --pkglibdir)
sharedir=$("$pg_config" --sharedir)
case "$pkglibdir" in "$pg_prefix"/*) lib_rel=${pkglibdir#"$pg_prefix"/} ;; *) echo "PostgreSQL library path is outside prefix: $pkglibdir" >&2; exit 1 ;; esac
case "$sharedir" in "$pg_prefix"/*) share_rel=${sharedir#"$pg_prefix"/} ;; *) echo "PostgreSQL share path is outside prefix: $sharedir" >&2; exit 1 ;; esac

payload="$work/payload/postgresql"
mkdir -p "$payload/$lib_rel" "$payload/$share_rel/extension"
module=
for candidate in "collection.so"; do
  if [[ -s "$stage$pkglibdir/$candidate" ]]; then module="$stage$pkglibdir/$candidate"; break; fi
done
[[ -n "$module" ]] || { echo "pgcollection did not install its module" >&2; exit 1; }
cp "$module" "$payload/$lib_rel/"
[[ -s "$stage$sharedir/extension/collection.control" ]] || {
  echo 'pgcollection did not install collection.control' >&2; exit 1;
}
shopt -s nullglob
extension_files=("$stage$sharedir"/extension/collection*)
[[ ${#extension_files[@]} -gt 0 ]] || { echo 'pgcollection did not install its extension files' >&2; exit 1; }
cp "${extension_files[@]}" "$payload/$share_rel/extension/"

pg_version=$("$pg_config" --version | sed 's/^PostgreSQL //')
archive="collection-postgresql-$pg_version-$target.tar.gz"
bash "$(dirname "${BASH_SOURCE[0]}")/../../shared/archive.sh" "$work/payload" "$output_dir/$archive"
