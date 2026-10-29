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
dependency_prefix="$(dirname "$pg_prefix")/dependencies"
[[ -d "$dependency_prefix/lib" ]] || { echo "Missing dependency library directory: $dependency_prefix/lib" >&2; exit 1; }
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
rust_selection=$(python3 - "$repo/support.json" <<'PY'
import json
import os
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    selected = json.load(source)["packages"]["pg_jsonschema"]["build_inputs"][os.environ["PG_BINARIES_TARGET"]]
print(selected["rust"], selected["cargo_pgrx"])
PY
)
read -r rust_version pgrx_version <<< "$rust_selection"
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/pg_jsonschema.XXXXXX")
trap 'rm -rf "$work"' EXIT

source_archive="$work/pg_jsonschema-$version.tar.gz"
bash "$(dirname "${BASH_SOURCE[0]}")/../../shared/fetch.sh" "$source_url" "$source_sha" "$source_archive"

archive_root=$(tar -tzf "$source_archive" | sed -n '1s,/.*,,p')
[[ "$archive_root" == "pg_jsonschema-$version" ]] || { echo "Unexpected source archive root: $archive_root" >&2; exit 1; }
tar -xzf "$source_archive" -C "$work"
source_dir="$work/pg_jsonschema-$version"
pg_config="$pg_prefix/bin/pg_config"
[[ -s "$source_dir/Cargo.lock" ]] || { echo 'pg_jsonschema source archive is missing Cargo.lock' >&2; exit 1; }
[[ $(sed -n 's/^version = "\([^"]*\)"/\1/p' "$source_dir/Cargo.toml" | head -n 1) == "$version" ]] || {
  echo 'Cargo.toml version does not match VERSION' >&2; exit 1;
}

export MACOSX_DEPLOYMENT_TARGET
export DYLD_LIBRARY_PATH="$dependency_prefix/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
export PGRX_HOME="$work/pgrx"
export PATH="$HOME/.cargo/bin:$PATH"
rustup toolchain install "$rust_version" --profile minimal
rustup run "$rust_version" cargo install cargo-pgrx --version "$pgrx_version" --locked
rustup run "$rust_version" cargo pgrx init --pg18 "$pg_config"
cd "$source_dir"
rustup run "$rust_version" cargo pgrx install --release --no-default-features --features pg18 --pg-config "$pg_config"

pkglibdir=$("$pg_config" --pkglibdir)
sharedir=$("$pg_config" --sharedir)
case "$pkglibdir" in "$pg_prefix"/*) lib_rel=${pkglibdir#"$pg_prefix"/} ;; *) echo "PostgreSQL library path is outside prefix: $pkglibdir" >&2; exit 1 ;; esac
case "$sharedir" in "$pg_prefix"/*) share_rel=${sharedir#"$pg_prefix"/} ;; *) echo "PostgreSQL share path is outside prefix: $sharedir" >&2; exit 1 ;; esac

payload="$work/payload/postgresql"
mkdir -p "$payload/$lib_rel" "$payload/$share_rel/extension"
module=
for candidate in pg_jsonschema.dylib pg_jsonschema.so; do
  if [[ -s "$pkglibdir/$candidate" ]]; then module="$pkglibdir/$candidate"; break; fi
done
[[ -n "$module" ]] || { echo 'pg_jsonschema did not install its module' >&2; exit 1; }
cp "$module" "$payload/$lib_rel/"
shopt -s nullglob
extension_files=("$sharedir"/extension/pg_jsonschema*)
[[ ${#extension_files[@]} -gt 0 ]] || { echo 'pg_jsonschema did not install its control and SQL files' >&2; exit 1; }
cp "${extension_files[@]}" "$payload/$share_rel/extension/"

pg_version=$("$pg_config" --version | sed 's/^PostgreSQL //')
archive="pg_jsonschema-postgresql-$pg_version-$target.tar.gz"
bash "$(dirname "${BASH_SOURCE[0]}")/../../shared/archive.sh" "$work/payload" "$output_dir/$archive"
