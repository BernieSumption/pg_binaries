#!/usr/bin/env bash
set -euo pipefail
pg_version=18.6
extension_version=0.3.4
extension_commit=cbe74b570d38aa0c4d42914e7a118bcb3adaee7a
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture:$(uname -m)" in x86_64:x86_64|arm64:aarch64) ;; *) echo "Architecture mismatch" >&2; exit 2 ;; esac
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
output_archive="pg_jsonschema-${extension_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
mkdir -p /work/core /work/source /out
tar -xzf "$pg_archive" -C /work/core
mv /work/core/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
git -C /work/source init -q
git -C /work/source remote add origin https://github.com/supabase/pg_jsonschema.git
git -C /work/source fetch --depth 1 origin "$extension_commit"
git -C /work/source checkout --detach FETCH_HEAD
test "$(git -C /work/source rev-parse HEAD)" = "$extension_commit"
test "$(sed -n 's/^version = "\([^"]*\)"/\1/p' /work/source/Cargo.toml | head -n 1)" = "$extension_version"
grep -Eq '^pg18 = \["pgrx/pg18", "pgrx-tests/pg18"\]$' /work/source/Cargo.toml
test -s /work/source/Cargo.lock
lock_sha256=$(sha256sum /work/source/Cargo.lock | awk '{print $1}')
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable
export PATH="/root/.cargo/bin:$pgroot/bin:$PATH"
export PGRX_HOME=/work/pgrx
cargo install cargo-pgrx --version 0.16.1 --locked
cargo pgrx init --pg18 "$pgroot/bin/pg_config"
cd /work/source
cargo pgrx install --release --no-default-features --features pg18 --pg-config "$pgroot/bin/pg_config"
test "$(sha256sum /work/source/Cargo.lock | awk '{print $1}')" = "$lock_sha256"
case "$architecture" in x86_64) rust_target=x86_64-unknown-linux-gnu ;; arm64) rust_target=aarch64-unknown-linux-gnu ;; esac
cargo metadata --locked --format-version 1 --filter-platform "$rust_target" \
  --no-default-features --features pg18 > /work/cargo-metadata.json
python3 /usr/local/bin/inventory-cargo-licenses /work/source /work/cargo-metadata.json \
  /out/cargo-license-inventory.json
test -s "$pgroot/lib/pg_jsonschema.so"
test -s "$pgroot/share/extension/pg_jsonschema.control"
tar -C /opt -czf "/out/$output_archive" postgresql
cd /out
sha256sum "$output_archive" > "$output_archive.sha256"
{
  printf 'pg_jsonschema_source_url=https://github.com/supabase/pg_jsonschema.git\n'
  printf 'pg_jsonschema_source_commit=%s\n' "$extension_commit"
  printf 'cargo_lock_sha256=%s\n' "$lock_sha256"
  rustc --version
  cargo --version
  "$pgroot/bin/pg_config" --version
} > /out/build-evidence.txt
