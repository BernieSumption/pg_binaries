#!/usr/bin/env bash
set -euo pipefail

dependency_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$dependency_dir/toolchain.sh"

pg_jsonschema_set_environment() {
  local workspace=$1
  export CARGO_HOME=${CARGO_HOME:-$HOME/.cargo}
  export RUSTUP_HOME=${RUSTUP_HOME:-$HOME/.rustup}
  export PATH="$CARGO_HOME/bin:$PATH"
  export PGRX_HOME="$workspace/build/pgrx"
  export CARGO_TARGET_DIR="$workspace/build/target"
  export PGRX_BUILD_FLAGS="--locked${PGRX_BUILD_FLAGS:+ $PGRX_BUILD_FLAGS}"
  export PG_JSONSCHEMA_TOOL_PREFIX="$CARGO_HOME/pg-binaries-tools/cargo-pgrx-$pgrx_version-rust-$rust_version"
  export PATH="$PG_JSONSCHEMA_TOOL_PREFIX/bin:$PATH"
}

pg_jsonschema_initialize_toolchain() {
  local workspace=$1 pg_config=$2
  pg_jsonschema_set_environment "$workspace"
  if ! command -v rustup >/dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs |
      sh -s -- -y --profile minimal --default-toolchain none --no-modify-path
  fi
  rustup toolchain install "$rust_version" --profile minimal
  if [[ ! -x "$PG_JSONSCHEMA_TOOL_PREFIX/bin/cargo-pgrx" ]]; then
    rustup run "$rust_version" cargo install cargo-pgrx --version "$pgrx_version" --locked --root "$PG_JSONSCHEMA_TOOL_PREFIX"
  fi
  local pg_version pg_major pg_feature
  pg_version=$("$pg_config" --version)
  pg_major=${pg_version#PostgreSQL }
  pg_feature="pg${pg_major%%.*}"
  rustup run "$rust_version" cargo pgrx init "--$pg_feature" "$pg_config"
}
