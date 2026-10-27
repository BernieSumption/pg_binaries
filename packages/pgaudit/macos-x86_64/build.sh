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
[[ $(uname -s) == Darwin && $(uname -m) == x86_64 ]] || { echo 'This recipe requires macOS x86_64' >&2; exit 1; }
: "${MACOSX_DEPLOYMENT_TARGET:?Set the selected minimum macOS version}"

pg_prefix=$(cd "$pg_prefix" && pwd)
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/pgaudit.XXXXXX")
trap 'rm -rf "$work"' EXIT

source_archive="$work/pgaudit-$version.tar.gz"
curl --fail --location --silent --show-error "$source_url" --output "$source_archive"
actual_sha=$(shasum -a 256 "$source_archive" | awk '{print $1}')
[[ "$actual_sha" == "$source_sha" ]] || { echo 'pgAudit source checksum mismatch' >&2; exit 1; }

archive_root=$(tar -tzf "$source_archive" | sed -n '1s,/.*,,p')
[[ "$archive_root" == "pgaudit-$version" ]] || { echo "Unexpected source archive root: $archive_root" >&2; exit 1; }
tar -xzf "$source_archive" -C "$work"
source_dir="$work/pgaudit-$version"
pg_config="$pg_prefix/bin/pg_config"
[[ $(sed -n "s/^default_version = '\([^']*\)'/\1/p" "$source_dir/pgaudit.control") == "$version" ]] || {
  echo 'pgAudit control-file version does not match VERSION' >&2; exit 1;
}

make -C "$source_dir" USE_PGXS=1 PG_CONFIG="$pg_config" -j "$(sysctl -n hw.ncpu)"
stage="$work/stage"
make -C "$source_dir" USE_PGXS=1 PG_CONFIG="$pg_config" DESTDIR="$stage" install

pkglibdir=$("$pg_config" --pkglibdir)
sharedir=$("$pg_config" --sharedir)
case "$pkglibdir" in "$pg_prefix"/*) lib_rel=${pkglibdir#"$pg_prefix"/} ;; *) echo "PostgreSQL library path is outside prefix: $pkglibdir" >&2; exit 1 ;; esac
case "$sharedir" in "$pg_prefix"/*) share_rel=${sharedir#"$pg_prefix"/} ;; *) echo "PostgreSQL share path is outside prefix: $sharedir" >&2; exit 1 ;; esac

payload="$work/payload/postgresql"
mkdir -p "$payload/$lib_rel" "$payload/$share_rel/extension"
module=
for candidate in "pgaudit.so" "pgaudit.dylib"; do
  if [[ -s "$stage$pkglibdir/$candidate" ]]; then module="$stage$pkglibdir/$candidate"; break; fi
done
[[ -n "$module" ]] || { echo "pgAudit did not install its module" >&2; exit 1; }
cp "$module" "$payload/$lib_rel/"
shopt -s nullglob
extension_files=("$stage$sharedir"/extension/pgaudit*)
[[ ${#extension_files[@]} -gt 0 ]] || { echo 'pgAudit did not install its extension files' >&2; exit 1; }
cp "${extension_files[@]}" "$payload/$share_rel/extension/"

printf '%s\n' 'See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md' > "$payload/LICENCE"
pg_version=$("$pg_config" --version | sed 's/^PostgreSQL //')
archive="pgaudit-postgresql-$pg_version-macos-x86_64.tar.gz"
tar -C "$work/payload" -czf "$output_dir/$archive" postgresql
shasum -a 256 "$output_dir/$archive" > "$output_dir/$archive.sha256"
echo "$output_dir/$archive"
