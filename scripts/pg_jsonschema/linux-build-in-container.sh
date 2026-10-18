#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
pg_major=${pg_version%%.*}
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
grep -Eq "^pg${pg_major} = \\[\"pgrx/pg${pg_major}\", \"pgrx-tests/pg${pg_major}\"\\]$" /work/source/Cargo.toml
test -s /work/source/Cargo.lock
lock_sha256=$(sha256sum /work/source/Cargo.lock | awk '{print $1}')
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable
export PATH="/root/.cargo/bin:$pgroot/bin:$PATH"
export PGRX_HOME=/work/pgrx
cd /work/source
case "$architecture" in x86_64) rust_target=x86_64-unknown-linux-gnu ;; arm64) rust_target=aarch64-unknown-linux-gnu ;; esac
cargo metadata --locked --format-version 1 --filter-platform "$rust_target" \
  --no-default-features --features "pg${pg_major}" > /work/cargo-metadata.json
python3 /usr/local/bin/inventory-cargo-licenses /work/source /work/cargo-metadata.json \
  /out/cargo-license-inventory.json
cargo install cargo-pgrx --version 0.16.1 --locked
cargo pgrx init "--pg${pg_major}" "$pgroot/bin/pg_config"
cargo pgrx install --release --no-default-features --features "pg${pg_major}" --pg-config "$pgroot/bin/pg_config"
test "$(sha256sum /work/source/Cargo.lock | awk '{print $1}')" = "$lock_sha256"
test -s "$pgroot/lib/pg_jsonschema.so"
test -s "$pgroot/share/extension/pg_jsonschema.control"
package=/work/package/pg_jsonschema
mkdir -p "$package/lib" "$package/share/extension" "$package/LICENSES/pg_jsonschema" "$package/LICENSES/cargo"
install -m 755 "$pgroot/lib/pg_jsonschema.so" "$package/lib/pg_jsonschema.so"
install -m 644 "$pgroot/share/extension/pg_jsonschema.control" "$package/share/extension/pg_jsonschema.control"
shopt -s nullglob
sql_files=("$pgroot/share/extension/pg_jsonschema--"*.sql)
(( ${#sql_files[@]} > 0 ))
install -m 644 "${sql_files[@]}" "$package/share/extension/"
if [[ -f /work/source/LICENSE ]]; then install -m 644 /work/source/LICENSE "$package/LICENSES/pg_jsonschema/LICENSE"; fi
python3 /usr/local/bin/inventory-cargo-licenses /work/source /work/cargo-metadata.json \
  /out/cargo-license-inventory.json --package-root "$package" --supplements /opt/cargo-license-supplements
cp /out/cargo-license-inventory.json "$package/LICENSES/cargo/cargo-license-inventory.json"
python3 - "$extension_version" "$pg_version" "$architecture" "$extension_commit" "$lock_sha256" <<'PY'
import json, pathlib, sys

version, pg_version, architecture, commit, lock_sha = sys.argv[1:]
metadata = {
    'project': 'pg_jsonschema', 'version': version, 'sql_names': ['pg_jsonschema'],
    'requires': [], 'configuration_prerequisites': [], 'runtime_prerequisites': [],
    'postgresql_version': pg_version, 'platform': 'linux', 'architecture': architecture,
    'source': {'url': 'https://github.com/supabase/pg_jsonschema.git', 'commit': commit,
               'cargo_lock_sha256': lock_sha},
    'release_eligible': False, 'redistribution_status': 'seahash-4.1.0-notice-unresolved',
}
pathlib.Path('/work/package/metadata.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
PY
tar -C /work/package -czf "/out/$output_archive" pg_jsonschema metadata.json
python3 /usr/local/bin/inventory-cargo-licenses --check-archive "/out/$output_archive" \
  --archive-inventory pg_jsonschema/LICENSES/cargo/cargo-license-inventory.json
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
