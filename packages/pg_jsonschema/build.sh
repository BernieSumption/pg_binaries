#!/usr/bin/env bash
set -euo pipefail

workspace=$3
source_dir="$workspace/sources/pg_jsonschema"
pg_prefix="$workspace/postgresql"
pg_config="$pg_prefix/bin/pg_config"
payload="$workspace/payload"
source "$(dirname "${BASH_SOURCE[0]}")/internal/toolchain.sh"

export CARGO_HOME=${CARGO_HOME:-$HOME/.cargo}
export RUSTUP_HOME=${RUSTUP_HOME:-$HOME/.rustup}
export PATH="$CARGO_HOME/bin:$PATH"
export PGRX_HOME="$workspace/build/pgrx"
export CARGO_TARGET_DIR="$workspace/build/target"
export PGRX_BUILD_FLAGS="--locked${PGRX_BUILD_FLAGS:+ $PGRX_BUILD_FLAGS}"

if ! command -v rustup >/dev/null; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs |
    sh -s -- -y --profile minimal --default-toolchain none --no-modify-path
fi
rustup toolchain install "$rust_version" --profile minimal

tool_prefix="$CARGO_HOME/pg-binaries-tools/cargo-pgrx-$pgrx_version-rust-$rust_version"
if [[ ! -x "$tool_prefix/bin/cargo-pgrx" ]]; then
  rustup run "$rust_version" cargo install cargo-pgrx --version "$pgrx_version" --locked --root "$tool_prefix"
fi
export PATH="$tool_prefix/bin:$PATH"

pg_version=$("$pg_config" --version)
pg_major=${pg_version#PostgreSQL }
pg_feature="pg${pg_major%%.*}"
rustup run "$rust_version" cargo pgrx init "--$pg_feature" "$pg_config"
cd "$source_dir"
rustup run "$rust_version" cargo pgrx install --release --no-default-features --features "$pg_feature" --pg-config "$pg_config"

pkglibdir=$("$pg_config" --pkglibdir)
sharedir=$("$pg_config" --sharedir)
lib_rel=${pkglibdir#"$pg_prefix"/}
share_rel=${sharedir#"$pg_prefix"/}
mkdir -p "$payload/$lib_rel" "$payload/$share_rel/extension"
find "$pkglibdir" -maxdepth 1 -type f \
  \( -name pg_jsonschema.so -o -name pg_jsonschema.dylib \) \
  -exec cp {} "$payload/$lib_rel/" \;
cp "$sharedir"/extension/pg_jsonschema*.control "$payload/$share_rel/extension/"
cp "$sharedir"/extension/pg_jsonschema*.sql "$payload/$share_rel/extension/"
