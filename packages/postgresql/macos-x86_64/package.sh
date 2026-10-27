#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 3 ]]; then
  echo "usage: $0 INSTALL_PREFIX DEPENDENCY_PREFIX OUTPUT_DIR" >&2
  exit 2
fi
install_prefix=$1
dependency_prefix=$2
output_dir=$3
[[ -x "$install_prefix/bin/pg_config" ]] || { echo "Missing PostgreSQL installation: $install_prefix" >&2; exit 1; }
[[ -d "$dependency_prefix/lib" ]] || { echo "Missing dependency prefix: $dependency_prefix" >&2; exit 1; }
[[ $(uname -s) == Darwin && $(uname -m) == x86_64 ]] || { echo 'This packager requires macOS x86_64' >&2; exit 1; }

install_prefix=$(cd "$install_prefix" && pwd)
dependency_prefix=$(cd "$dependency_prefix" && pwd)
[[ $(basename "$install_prefix") == postgresql ]] || { echo 'INSTALL_PREFIX must end in postgresql' >&2; exit 2; }
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
version=$("$install_prefix/bin/pg_config" --version)
version=${version#PostgreSQL }

work=$(mktemp -d "${TMPDIR:-/tmp}/postgresql-package.XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/runtime/postgresql"
cp -R "$install_prefix"/. "$work/runtime/postgresql/"
rm -rf "$work/runtime/postgresql/include" "$work/runtime/postgresql/lib/pgxs"
rm -f "$work/runtime/postgresql/bin/pg_config"
find "$work/runtime/postgresql/lib" -maxdepth 1 -name '*.a' -delete

python3 "$repo_root/platforms/macos/bundle.py" "$work/runtime/postgresql" "$dependency_prefix"
printf '%s\n' 'See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md' > "$work/runtime/postgresql/LICENCE"

mkdir -p "$work/development/postgresql" "$work/development/dependencies"
cp -R "$install_prefix"/. "$work/development/postgresql/"
cp -R "$dependency_prefix"/. "$work/development/dependencies/"

export COPYFILE_DISABLE=1
runtime_archive="postgresql-$version-macos-x86_64.tar.gz"
development_archive="postgresql-development-$version-macos-x86_64.tar.gz"
tar -C "$work/runtime" -czf "$output_dir/$runtime_archive" postgresql
tar -C "$work/development" -czf "$output_dir/$development_archive" postgresql dependencies
(cd "$output_dir" && shasum -a 256 "$runtime_archive" "$development_archive") > "$output_dir/checksums.sha256"
echo "$output_dir/$runtime_archive"
echo "$output_dir/$development_archive"
