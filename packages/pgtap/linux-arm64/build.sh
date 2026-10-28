#!/usr/bin/env bash
set -euo pipefail
[[ $# == 5 ]] || { echo "usage: $0 SOURCE_URL SOURCE_SHA256 VERSION POSTGRESQL_PREFIX OUTPUT_DIR" >&2; exit 2; }
source_url=$1 source_sha=$2 version=$3 pg_prefix=$4 output_dir=$5
[[ $source_sha =~ ^[0-9a-f]{64}$ && $version =~ ^[0-9]+(\.[0-9]+)+$ ]] || { echo 'Invalid source checksum or version' >&2; exit 2; }
[[ $(uname -s) == Linux && $(uname -m) == aarch64 ]] || { echo 'This recipe requires Linux ARM64' >&2; exit 1; }
[[ -x $pg_prefix/bin/pg_config ]] || { echo "Missing pg_config under $pg_prefix" >&2; exit 1; }
pg_prefix=$(cd "$pg_prefix" && pwd); mkdir -p "$output_dir"; output_dir=$(cd "$output_dir" && pwd)
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
curl -fsSL "$source_url" -o "$work/source.tar.gz"; echo "$source_sha  $work/source.tar.gz" | sha256sum -c -
[[ $(tar -tzf "$work/source.tar.gz" | sed -n '1s,/.*,,p') == "pgtap-$version" ]]
tar -xzf "$work/source.tar.gz" -C "$work"; src="$work/pgtap-$version"; pg_config="$pg_prefix/bin/pg_config"
[[ $(sed -n "s/^default_version = '\([^']*\)'/\1/p" "$src/pgtap.control") == "$version" ]]
make -C "$src" USE_PGXS=1 PG_CONFIG="$pg_config" -j "$(nproc)"
stage="$work/stage"; make -C "$src" USE_PGXS=1 PG_CONFIG="$pg_config" DESTDIR="$stage" install
sharedir=$("$pg_config" --sharedir); case $sharedir in "$pg_prefix"/*) share_rel=${sharedir#"$pg_prefix"/};; *) exit 1;; esac
payload="$work/payload/postgresql"; mkdir -p "$payload/$share_rel/extension"
cp "$stage$sharedir"/extension/pgtap* "$payload/$share_rel/extension/"
[[ -s "$payload/$share_rel/extension/pgtap.control" ]]
printf '%s\n' 'See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md' > "$payload/LICENCE"
pg_version=$("$pg_config" --version | sed 's/^PostgreSQL //'); archive="pgtap-postgresql-$pg_version-linux-arm64.tar.gz"
tar -C "$work/payload" -czf "$output_dir/$archive" postgresql; sha256sum "$output_dir/$archive" > "$output_dir/$archive.sha256"; echo "$output_dir/$archive"
