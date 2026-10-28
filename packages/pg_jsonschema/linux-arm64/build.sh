#!/usr/bin/env bash
set -euo pipefail
[[ $# == 5 ]] || { echo "usage: $0 SOURCE_URL SOURCE_SHA256 VERSION POSTGRESQL_PREFIX OUTPUT_DIR" >&2; exit 2; }
source_url=$1 source_sha=$2 version=$3 pg_prefix=$4 output_dir=$5
[[ $source_sha =~ ^[0-9a-f]{64}$ && $version =~ ^[0-9]+(\.[0-9]+)+$ ]] || { echo 'Invalid source checksum or version' >&2; exit 2; }
[[ $(uname -s) == Linux && $(uname -m) == aarch64 ]] || { echo 'This recipe requires Linux ARM64' >&2; exit 1; }
[[ -x $pg_prefix/bin/pg_config ]] || { echo "Missing pg_config under $pg_prefix" >&2; exit 1; }
pg_prefix=$(cd "$pg_prefix" && pwd); repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
read -r rust_version pgrx_version < <(python3 - "$repo/support.json" <<'PY'
import json,sys
s=json.load(open(sys.argv[1]))['packages']['pg_jsonschema']['build_inputs']['linux-arm64']
print(s['rust'],s['cargo_pgrx'])
PY
)
mkdir -p "$output_dir"; output_dir=$(cd "$output_dir" && pwd); work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
curl -fsSL "$source_url" -o "$work/source.tar.gz"; echo "$source_sha  $work/source.tar.gz" | sha256sum -c -
[[ $(tar -tzf "$work/source.tar.gz" | sed -n '1s,/.*,,p') == "pg_jsonschema-$version" ]]
tar -xzf "$work/source.tar.gz" -C "$work"; src="$work/pg_jsonschema-$version"
[[ -s "$src/Cargo.lock" && $(sed -n 's/^version = "\([^"]*\)"/\1/p' "$src/Cargo.toml" | head -n1) == "$version" ]]
export CARGO_HOME=${CARGO_HOME:-$work/cargo} RUSTUP_HOME=${RUSTUP_HOME:-$work/rustup} PGRX_HOME=${PGRX_HOME:-$work/pgrx}
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain "$rust_version"
export PATH="$CARGO_HOME/bin:$PATH"
cargo install cargo-pgrx --version "$pgrx_version" --locked
cargo pgrx init --pg18 "$pg_prefix/bin/pg_config"
(cd "$src" && cargo pgrx install --release --no-default-features --features pg18 --pg-config "$pg_prefix/bin/pg_config")
pkglibdir=$("$pg_prefix/bin/pg_config" --pkglibdir); sharedir=$("$pg_prefix/bin/pg_config" --sharedir)
case $pkglibdir in "$pg_prefix"/*) lib_rel=${pkglibdir#"$pg_prefix"/};; *) exit 1;; esac
case $sharedir in "$pg_prefix"/*) share_rel=${sharedir#"$pg_prefix"/};; *) exit 1;; esac
payload="$work/payload/postgresql"; mkdir -p "$payload/$lib_rel" "$payload/$share_rel/extension"
cp "$pkglibdir/pg_jsonschema.so" "$payload/$lib_rel/"
cp "$sharedir"/extension/pg_jsonschema* "$payload/$share_rel/extension/"
printf '%s\n' 'See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md' > "$payload/LICENCE"
pg_version=$("$pg_prefix/bin/pg_config" --version | sed 's/^PostgreSQL //'); archive="pg_jsonschema-postgresql-$pg_version-linux-arm64.tar.gz"
tar -C "$work/payload" -czf "$output_dir/$archive" postgresql; sha256sum "$output_dir/$archive" > "$output_dir/$archive.sha256"; echo "$output_dir/$archive"
