#!/usr/bin/env bash
set -euo pipefail

pg_version=18.6
vector_version=0.8.7
script_dir=$(cd "$(dirname "$0")" && pwd)
output_dir=$(mkdir -p "${1:?output directory required}" && cd "$1" && pwd)
work_dir=$(mktemp -d "${RUNNER_TEMP:-/tmp}/pg-macos-pilot.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT

if [[ $(uname -s) != Darwin || $(uname -m) != x86_64 ]]; then
  echo 'This build requires Intel macOS' >&2
  exit 1
fi

brew install icu4c openssl@3 lz4 zstd libxml2 libxslt
brew_prefixes=()
pkgconfig_paths=()
for formula in icu4c openssl@3 lz4 zstd libxml2 libxslt; do
  prefix=$(brew --prefix "$formula")
  brew_prefixes+=("$prefix")
  pkgconfig_paths+=("$prefix/lib/pkgconfig")
done
export PKG_CONFIG_PATH=$(IFS=:; echo "${pkgconfig_paths[*]}")
export CPPFLAGS=""
export LDFLAGS=" -Wl,-headerpad_max_install_names"
for prefix in "${brew_prefixes[@]}"; do
  CPPFLAGS+=" -I$prefix/include"
  LDFLAGS+=" -L$prefix/lib"
done
export CPPFLAGS LDFLAGS

curl -fL --retry 3 "https://ftp.postgresql.org/pub/source/v${pg_version}/postgresql-${pg_version}.tar.bz2" -o "$work_dir/postgresql.tar.bz2"
curl -fL --retry 3 "https://github.com/pgvector/pgvector/archive/refs/tags/v${vector_version}.tar.gz" -o "$work_dir/pgvector.tar.gz"
tar -xjf "$work_dir/postgresql.tar.bz2" -C "$work_dir"
tar -xzf "$work_dir/pgvector.tar.gz" -C "$work_dir"

install_dir="$work_dir/install/postgresql"
cd "$work_dir/postgresql-${pg_version}"
./configure --prefix="$install_dir" --with-icu --with-ssl=openssl --with-lz4 --with-zstd --with-libxml --with-libxslt --without-readline
make -j "$(sysctl -n hw.ncpu)"
make -C contrib -j "$(sysctl -n hw.ncpu)"
make install
make -C contrib install

package_dir="$work_dir/package"
mkdir -p "$package_dir/postgresql/LICENSES" "$package_dir/pgvector/lib" "$package_dir/pgvector/share/extension" "$package_dir/pgvector/LICENSES"
cp -R "$install_dir"/. "$package_dir/postgresql/"
cp "$work_dir/postgresql-${pg_version}/COPYRIGHT" "$package_dir/postgresql/LICENSES/PostgreSQL.txt"
python3 "$script_dir/bundle.py" "$package_dir/postgresql"
python3 "$script_dir/licenses.py" "$package_dir/postgresql"

cat > "$package_dir/postgresql/manifest.json" <<EOF
{
  "schema_version": 1,
  "component": "postgresql",
  "version": "$pg_version",
  "postgresql_version": "$pg_version",
  "platform": "macos",
  "architecture": "x86_64",
  "capabilities": ["icu", "libc_collations", "lz4", "zstd_wal"]
}
EOF

cd "$work_dir/pgvector-${vector_version}"
make PG_CONFIG="$install_dir/bin/pg_config" -j "$(sysctl -n hw.ncpu)"
make PG_CONFIG="$install_dir/bin/pg_config" install
cp "$install_dir/lib/vector.dylib" "$package_dir/pgvector/lib/"
cp "$install_dir/share/extension/vector"* "$package_dir/pgvector/share/extension/"
cp LICENSE "$package_dir/pgvector/LICENSES/pgvector.txt"
python3 "$script_dir/bundle.py" "$package_dir/pgvector"
python3 "$script_dir/licenses.py" "$package_dir/pgvector"

cat > "$package_dir/pgvector/manifest.json" <<EOF
{
  "schema_version": 1,
  "component": "pgvector",
  "version": "$vector_version",
  "postgresql_version": "$pg_version",
  "platform": "macos",
  "architecture": "x86_64"
}
EOF

pg_archive="postgresql-${pg_version}-macos-x86_64.tar.gz"
vector_archive="pgvector-${vector_version}-postgresql-${pg_version}-macos-x86_64.tar.gz"
tar -C "$package_dir" -czf "$output_dir/$pg_archive" postgresql
tar -C "$package_dir" -czf "$output_dir/$vector_archive" pgvector
cd "$output_dir"
shasum -a 256 "$pg_archive" > "$pg_archive.sha256"
shasum -a 256 "$vector_archive" > "$vector_archive.sha256"
ls -lh "$pg_archive" "$vector_archive"
