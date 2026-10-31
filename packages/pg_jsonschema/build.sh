#!/usr/bin/env bash
set -euo pipefail

workspace=$3
source_dir="$workspace/sources/pg_jsonschema"
pg_prefix="$workspace/postgresql"
pg_config="$pg_prefix/bin/pg_config"
payload="$workspace/payload"
source "$(dirname "${BASH_SOURCE[0]}")/internal/dependencies/environment.sh"
pg_jsonschema_set_environment "$workspace"

hook="$(dirname "${BASH_SOURCE[0]}")/internal/build.rs"
if ! cmp -s "$hook" "$source_dir/build.rs"; then cp "$hook" "$source_dir/build.rs"; fi
pg_version=$("$pg_config" --version)
pg_major=${pg_version#PostgreSQL }
pg_feature="pg${pg_major%%.*}"
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
