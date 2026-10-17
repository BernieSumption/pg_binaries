#!/usr/bin/env bash
set -euo pipefail

output=${1:?usage: macos-probe.sh OUTPUT_DIRECTORY [EXPECTED_ARCH]}
expected_arch=${2:-x86_64}
case "$expected_arch" in x86_64|arm64) ;; *)
  echo "Unsupported architecture: $expected_arch" >&2
  exit 2
esac
actual_arch=$(uname -m)
test "$actual_arch" = "$expected_arch" || {
  echo "Expected native $expected_arch runner, got $actual_arch" >&2
  exit 1
}
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
work=${RUNNER_TEMP:-${TMPDIR:-/tmp}}/pg-jsonschema-macos-$expected_arch
prefix="$work/postgres"
source="$work/source"
mkdir -p "$source" "$work/socket"

pg_version=18.6
extension_version=0.3.4
extension_tag=v0.3.4
expected_commit=cbe74b570d38aa0c4d42914e7a118bcb3adaee7a
deployment_target=11.0
export MACOSX_DEPLOYMENT_TARGET=$deployment_target
export PATH="$prefix/bin:$HOME/.cargo/bin:$PATH"
export PGRX_HOME="$work/pgrx"

cd "$source"
curl -fL --retry 3 -o "postgresql-$pg_version.tar.gz" \
  "https://ftp.postgresql.org/pub/source/v$pg_version/postgresql-$pg_version.tar.gz"
curl -fL --retry 3 -o "postgresql-$pg_version.tar.gz.sha256" \
  "https://ftp.postgresql.org/pub/source/v$pg_version/postgresql-$pg_version.tar.gz.sha256"
pg_sha=$(awk -v name="postgresql-$pg_version.tar.gz" '$2 == name {print $1}' "postgresql-$pg_version.tar.gz.sha256")
test -n "$pg_sha"
printf '%s  %s\n' "$pg_sha" "postgresql-$pg_version.tar.gz" | shasum -a 256 -c -
tar -xzf "postgresql-$pg_version.tar.gz"
cd "postgresql-$pg_version"
./configure --prefix="$prefix" --without-icu --without-readline --without-zlib
make -s -j"$(sysctl -n hw.ncpu)"
make -s install

cd "$source"
git clone --depth 1 --branch "$extension_tag" \
  https://github.com/supabase/pg_jsonschema.git pg_jsonschema
cd pg_jsonschema
extension_commit=$(git rev-parse HEAD)
case "$extension_commit" in "$expected_commit") ;; *)
  echo "Unexpected $extension_tag commit: $extension_commit" >&2
  exit 1
esac
test "$(sed -n 's/^version = "\([^"]*\)"/\1/p' Cargo.toml | head -n 1)" = "$extension_version"
grep -Eq '^pg18 = \["pgrx/pg18", "pgrx-tests/pg18"\]$' Cargo.toml
test -f Cargo.lock
cargo install cargo-pgrx --version 0.16.1 --locked
cargo pgrx init --pg18 "$prefix/bin/pg_config"
cargo pgrx install --release --no-default-features --features pg18 \
  --pg-config "$prefix/bin/pg_config"

"$prefix/bin/initdb" -D "$work/data" --encoding=UTF8 --locale=C --no-instructions
"$prefix/bin/pg_ctl" -D "$work/data" -o "-k $work/socket -p 55432 -h ''" -w start
stop_server() { "$prefix/bin/pg_ctl" -D "$work/data" -m immediate stop >/dev/null 2>&1 || true; }
trap stop_server EXIT
"$prefix/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 \
  -d postgres -f "$script_dir/probe.sql" | tee "$output/probe-output.txt"
"$prefix/bin/pg_ctl" -D "$work/data" -m fast -w stop
trap - EXIT

pkglibdir=$("$prefix/bin/pg_config" --pkglibdir)
extension_dylib=$(find "$pkglibdir" -maxdepth 1 -type f \( -name '*jsonschema*.so' -o -name '*jsonschema*.dylib' \) -print -quit)
test -n "$extension_dylib" && test -f "$extension_dylib"
{
  echo "architecture=$(uname -m)"
  echo "macos_version=$(sw_vers -productVersion)"
  echo "deployment_target=$deployment_target"
  echo "postgresql_version=$pg_version"
  echo "postgresql_source_sha256=$pg_sha"
  echo "pg_jsonschema_version=$extension_version"
  echo "pg_jsonschema_tag=$extension_tag"
  echo "pg_jsonschema_commit=$extension_commit"
  echo "cargo_lock_sha256=$(shasum -a 256 Cargo.lock | awk '{print $1}')"
  rustc --version
  cargo --version
  echo "--- $extension_dylib"
  lipo -archs "$extension_dylib"
  otool -l "$extension_dylib" | awk '
    /cmd LC_BUILD_VERSION/ {build=1; next}
    build && /minos / {print "minos " $2; build=0}
    /cmd LC_VERSION_MIN_MACOSX/ {legacy=1; next}
    legacy && /version / {print "minos " $2; legacy=0}
  '
  otool -L "$extension_dylib"
} | tee "$output/macho-inspection.txt"

lipo -archs "$extension_dylib" | grep -Eq "(^| )$expected_arch( |$)"
minimum=$(otool -l "$extension_dylib" | awk '/cmd LC_BUILD_VERSION/ {build=1; next} build && /minos / {print $2; exit} /cmd LC_VERSION_MIN_MACOSX/ {legacy=1; next} legacy && /version / {print $2; exit}')
test -n "$minimum"
awk -v version="$minimum" 'BEGIN {split(version,a,"."); if (a[1] > 11 || (a[1] == 11 && a[2] > 0)) exit 1}'
if otool -L "$extension_dylib" | grep -E '/opt/homebrew/|/usr/local/opt/'; then
  echo "Probe dylib links to a Homebrew dependency: $extension_dylib" >&2
  exit 1
fi
