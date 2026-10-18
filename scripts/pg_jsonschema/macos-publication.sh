#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-publication.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
output=${2:?usage: macos-publication.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
target_config=${3:?usage: macos-publication.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
source "$repo/scripts/macos/compiled-prefix-relocation.sh"
if [[ $target_config != /* ]]; then target_config="$repo/$target_config"; fi
target_values=$(python3 - "$repo/tools" "$target_config" <<'PYTARGET'
import sys
sys.path.insert(0, sys.argv[1])
from pg_jsonschema_macos_target import load_target
print("\t".join(load_target(sys.argv[2]).shell_values()))
PYTARGET
)
IFS=$'\t' read -r pg_version extension_version architecture platform profile_id core_name core_run_id \
  core_sha256 core_build_id core_revision source_url extension_commit cargo_lock_sha256 <<< "$target_values"
pg_major=${pg_version%%.*}
feature="pg$pg_major"
cargo_target=$(python3 - "$repo/tools" "$target_config" <<'PYTARGET'
import sys
sys.path.insert(0, sys.argv[1])
from pg_jsonschema_macos_target import load_target
print(load_target(sys.argv[2]).cargo_target)
PYTARGET
)
extension_name="pg_jsonschema-${extension_version}-postgresql-${pg_version}-${platform}.tar.gz"
deployment_target=11.0
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This candidate requires native macOS $architecture" >&2
  exit 1
fi
core_archives=$(cd "$core_archives" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
test -s "$core_archives/$core_name" && test -s "$core_archives/$core_name.sha256"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_archives" && shasum -a 256 -c -)

work=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/pg-jsonschema-macos.XXXXXX")
prefix_link_created=false
server_data=
testroot=
cleanup() {
  if [[ -n ${server_data:-} && -n ${testroot:-} ]]; then
    "$testroot/bin/pg_ctl" -D "$server_data" -m immediate -w stop >/dev/null 2>&1 || true
  fi
  macos_restore_compiled_prefix || true
  if [[ $prefix_link_created == true && -n ${prefix_link:-} && -L $prefix_link ]]; then
    rm "$prefix_link"
  fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/core" "$work/source" "$work/package" "$work/test-core" "$work/socket"
tar -xzf "$core_archives/$core_name" -C "$work/core"
pgroot="$work/core/postgresql"
test -s "$pgroot/bin/pg_config"

python3 - "$pgroot" "$pg_version" "$architecture" "$core_build_id" "$core_revision" > "$work/core-prefix" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
pg_version, architecture, build_id, source_revision = sys.argv[2:]
manifest = json.loads((root / "manifest.json").read_text())
expected = {"component": "postgresql", "version": pg_version, "postgresql_version": pg_version,
            "platform": "macos", "architecture": architecture, "build_id": build_id,
            "source_revision": source_revision}
for key, value in expected.items():
    if manifest.get(key) != value:
        raise SystemExit(f"PostgreSQL core manifest mismatch for {key}")
header = (root / "include/server/pg_config.h").read_text()
match = re.search(r'#define CONFIGURE_ARGS "[^\n]*?--prefix=([^\']+)', header)
if not match:
    raise SystemExit("cannot read PostgreSQL archive installation prefix")
prefix = pathlib.Path(match.group(1))
if not re.fullmatch(r"/Users/runner/work/_temp/pg-macos-pilot\.[A-Za-z0-9]+/install/postgresql", str(prefix)):
    raise SystemExit(f"unexpected PostgreSQL archive installation prefix: {prefix}")
print(prefix)
PY
prefix=$(cat "$work/core-prefix")
if [[ -e "$prefix" || -L "$prefix" ]]; then
  echo "Refusing to replace existing PostgreSQL prefix path: $prefix" >&2
  exit 1
fi
mkdir -p "$(dirname "$prefix")"
ln -s "$pgroot" "$prefix"
prefix_link=$prefix
prefix_link_created=true

export MACOSX_DEPLOYMENT_TARGET=$deployment_target
export PGRX_HOME="$work/pgrx"
export PATH="$prefix/bin:$HOME/.cargo/bin:$PATH"
cd "$work/source"
git init -q pg_jsonschema
git -C pg_jsonschema remote add origin "$source_url"
git -C pg_jsonschema fetch --depth 1 origin "$extension_commit"
git -C pg_jsonschema checkout --detach FETCH_HEAD
test "$(git -C pg_jsonschema rev-parse HEAD)" = "$extension_commit"
cd "$work/source/pg_jsonschema"
test "$(sed -n 's/^version = "\([^"]*\)"/\1/p' Cargo.toml | head -n 1)" = "$extension_version"
grep -Fqx "$feature = [\"pgrx/$feature\", \"pgrx-tests/$feature\"]" Cargo.toml
test -s Cargo.lock
actual_lock_sha256=$(shasum -a 256 Cargo.lock | awk '{print $1}')
test "$actual_lock_sha256" = "$cargo_lock_sha256"
cargo metadata --locked --format-version 1 --filter-platform "$cargo_target" \
  --no-default-features --features "$feature" > "$work/cargo-metadata.json"
python3 "$repo/tools/inventory_cargo_licenses.py" "$work/source/pg_jsonschema" \
  "$work/cargo-metadata.json" "$output/cargo-license-inventory.json"
cargo install cargo-pgrx --version 0.16.1 --locked
cargo pgrx init "--pg$pg_major" "$prefix/bin/pg_config"
cargo pgrx install --release --no-default-features --features "$feature" --pg-config "$prefix/bin/pg_config"
test "$(shasum -a 256 Cargo.lock | awk '{print $1}')" = "$cargo_lock_sha256"

pkglibdir=$("$prefix/bin/pg_config" --pkglibdir)
extensiondir=$("$prefix/bin/pg_config" --sharedir)/extension
extension_dylib=$(find "$pkglibdir" -maxdepth 1 -type f \( -name 'pg_jsonschema.dylib' -o -name 'pg_jsonschema.so' \) -print -quit)
test -n "$extension_dylib" && test -s "$extension_dylib"
mkdir -p "$work/package/pg_jsonschema/lib" "$work/package/pg_jsonschema/share/extension" \
  "$work/package/pg_jsonschema/LICENSES"
cp "$extension_dylib" "$work/package/pg_jsonschema/lib/pg_jsonschema.dylib"
cp "$extensiondir/pg_jsonschema.control" "$work/package/pg_jsonschema/share/extension/"
find "$extensiondir" -maxdepth 1 -type f -name 'pg_jsonschema*.sql' -exec cp {} "$work/package/pg_jsonschema/share/extension/" \;
cp "$work/source/pg_jsonschema/LICENSE" "$work/package/pg_jsonschema/LICENSES/pg_jsonschema.txt"
python3 "$repo/tools/inventory_cargo_licenses.py" "$work/source/pg_jsonschema" \
  "$work/cargo-metadata.json" "$output/cargo-license-inventory.json" \
  --package-root "$work/package/pg_jsonschema" \
  --supplements "$repo/support/evidence/pg-jsonschema-crate-licenses-2026-10-18"
cp "$output/cargo-license-inventory.json" \
  "$work/package/pg_jsonschema/LICENSES/pg_jsonschema-cargo-license-inventory.json"

python3 - "$work/package" "$core_sha256" "$cargo_lock_sha256" "$pg_version" "$architecture" "$platform" "$source_url" "$extension_commit" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
core_sha256, cargo_lock_sha256, pg_version, architecture, platform, source_url, extension_commit = sys.argv[2:]
metadata = {
    "project": "pg_jsonschema", "version": "0.3.4", "sql_names": ["pg_jsonschema"],
    "requires": [], "postgresql_version": pg_version, "platform": "macos", "architecture": architecture,
    "source": {"url": source_url, "commit": extension_commit,
               "cargo_lock_sha256": cargo_lock_sha256},
    "core_archive": {"basename": f"postgresql-{pg_version}-{platform}.tar.gz", "sha256": core_sha256},
    "release_eligible": False,
    "release_blockers": ["seahash-4.1.0-notice-unresolved",
                         "postgresql-core-redistribution-review-pending"],
}
(root / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
PY
tar -C "$work/package" -czf "$output/$extension_name" pg_jsonschema metadata.json
python3 "$repo/tools/inventory_cargo_licenses.py" --check-archive "$output/$extension_name" \
  --archive-inventory pg_jsonschema/LICENSES/pg_jsonschema-cargo-license-inventory.json
(cd "$output" && shasum -a 256 "$extension_name" > "$extension_name.sha256")

python3 - "$work/package" "$work/test-core" "$core_archives/$core_name" "$output/$extension_name" <<'PY'
import pathlib
import sys
import tarfile

package, extraction = map(pathlib.Path, sys.argv[1:3])
extension_archive = pathlib.Path(sys.argv[4])
with tarfile.open(extension_archive, "r:gz") as archive:
    seen = set()
    for member in archive.getmembers():
        path = pathlib.PurePosixPath(member.name)
        if member.name in seen or path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
            raise SystemExit(f"unsafe pg_jsonschema archive member: {member.name}")
        seen.add(member.name)
    archive.extractall(extraction)
payload = extraction / "pg_jsonschema"
required = {"lib/pg_jsonschema.dylib", "share/extension/pg_jsonschema.control",
            "LICENSES/pg_jsonschema.txt", "LICENSES/pg_jsonschema-cargo-license-inventory.json"}
if not required <= {path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file()}:
    raise SystemExit("pg_jsonschema final archive is missing required payload files")
core = pathlib.Path(sys.argv[3])
with tarfile.open(core, "r:gz") as archive:
    archive.extractall(extraction / "core")
PY
test -d "$work/test-core/core/postgresql"
testroot="$work/test-core/core/postgresql"
python3 - "$work/test-core/pg_jsonschema" "$testroot" <<'PY'
import pathlib
import sys

payload, target = map(pathlib.Path, sys.argv[1:])
for source in payload.rglob("*"):
    if source.is_dir():
        continue
    relative = source.relative_to(payload)
    destination = target / relative
    if destination.exists() or destination.is_symlink():
        raise SystemExit(f"pg_jsonschema archive collides with PostgreSQL core: {relative}")
for source in payload.rglob("*"):
    destination = target / source.relative_to(payload)
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
PY
mkdir -p "$work/relocated"
mv "$testroot" "$work/relocated/postgresql"
testroot="$work/relocated/postgresql"
python3 "$repo/scripts/macos/static_analysis.py" "$testroot" "$architecture" \
  --archive "$core_archives/$core_name" --archive "$output/$extension_name" \
  --report "$output/static-analysis.json"

mkdir -p "$work/data"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
macos_hide_compiled_prefix "$prefix" "$pgroot"
test ! -e "$prefix" && test ! -L "$prefix"
"$testroot/bin/initdb" -D "$work/data" --encoding=UTF8 --locale=C --no-instructions >/dev/null
"$testroot/bin/pg_ctl" -D "$work/data" -l "$work/server.log" \
  -o "-k $work/socket -p 55432 -h ''" -w start
server_data="$work/data"
"$testroot/bin/psql" -X -A -t -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 \
  -d postgres -f "$repo/scripts/pg_jsonschema/probe.sql" | tee "$output/probe-output.txt"
grep -Fxq 'pg_jsonschema|0.3.4' "$output/probe-output.txt"
"$testroot/bin/pg_ctl" -D "$work/data" -m fast -w stop
server_data=
macos_restore_compiled_prefix
prefix_link_created=true
{
  echo "pg_jsonschema_source_url=$source_url"
  echo "pg_jsonschema_source_commit=$extension_commit"
  echo "profile_id=$profile_id"
  echo "cargo_lock_sha256=$cargo_lock_sha256"
  echo "core_run_id=$core_run_id"
  echo "core_build_id=$core_build_id"
  echo "core_source_revision=$core_revision"
  echo "core_sha256=$core_sha256"
  echo "deployment_target=$deployment_target"
  echo "macos_version=$(sw_vers -productVersion)"
  echo "architecture=$(uname -m)"
  echo "core_archive=$core_name"
  rustc --version
  cargo --version
  "$testroot/bin/pg_config" --version
} | tee "$output/build-evidence.txt"
echo "PASS: pg_jsonschema $extension_version packaged, relocated, inspected and exercised with PostgreSQL $pg_version on macOS $architecture"
