#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: verify-macos-publication.sh CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
extension_archives=${2:?usage: verify-macos-publication.sh CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
output=${3:?usage: verify-macos-publication.sh CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
target_config=${4:?usage: verify-macos-publication.sh CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
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
  core_sha256 core_build_id core_revision source_url extension_commit cargo_lock_sha256 module_filename <<< "$target_values"
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This candidate requires native macOS $architecture" >&2
  exit 1
fi
core_archives=$(cd "$core_archives" && pwd)
extension_archives=$(cd "$extension_archives" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
extension_name="pg_jsonschema-${extension_version}-postgresql-${pg_version}-${platform}.tar.gz"
test -s "$core_archives/$core_name" && test -s "$core_archives/$core_name.sha256"
test -s "$extension_archives/$extension_name" && test -s "$extension_archives/$extension_name.sha256"
test -s "$extension_archives/build-evidence.txt"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
(cd "$extension_archives" && shasum -a 256 -c "$extension_name.sha256")
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_archives" && shasum -a 256 -c -)

work=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/pg-jsonschema-verify.XXXXXX")
prefix_link_created=false
server_data=
cleanup() {
  if [[ -n ${server_data:-} && -n ${testroot:-} ]]; then
    "$testroot/bin/pg_ctl" -D "$server_data" -m immediate -w stop >/dev/null 2>&1 || true
  fi
  macos_restore_compiled_prefix || true
  if [[ $prefix_link_created == true && -n ${prefix_link:-} && -L $prefix_link ]]; then rm "$prefix_link"; fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/core" "$work/extension" "$work/merged" "$work/compiled-prefix" "$work/socket"
python3 - "$core_archives/$core_name" "$extension_archives/$extension_name" "$work/core" "$work/extension" <<'PY'
import pathlib
import sys
import tarfile

for archive_path, destination in zip(map(pathlib.Path, sys.argv[1:3]), map(pathlib.Path, sys.argv[3:5])):
    with tarfile.open(archive_path, "r:gz") as archive:
        seen = set()
        for member in archive.getmembers():
            path = pathlib.PurePosixPath(member.name)
            if (member.name in seen or path.is_absolute() or ".." in path.parts
                    or member.issym() or member.islnk()):
                raise SystemExit(f"unsafe archive member in {archive_path.name}: {member.name}")
            seen.add(member.name)
        archive.extractall(destination)
PY
python3 - "$work/extension/metadata.json" "$core_name" "$core_sha256" "$pg_version" \
  "$architecture" "$source_url" "$extension_commit" "$cargo_lock_sha256" <<'PY'
import json, pathlib, sys
metadata = json.loads(pathlib.Path(sys.argv[1]).read_text())
core, digest, pg_version, architecture, source_url, commit, lock_hash = sys.argv[2:]
expected = {"project": "pg_jsonschema", "version": "0.3.4", "sql_names": ["pg_jsonschema"],
            "requires": [], "postgresql_version": pg_version, "platform": "macos",
            "architecture": architecture,
            "source": {"url": source_url, "commit": commit, "cargo_lock_sha256": lock_hash},
            "core_archive": {"basename": core, "sha256": digest}, "release_eligible": False,
            "release_blockers": ["seahash-4.1.0-notice-unresolved",
                                  "postgresql-core-redistribution-review-pending"]}
if metadata != expected: raise SystemExit("pg_jsonschema archive metadata differs from the selected target")
PY
pgroot="$work/core/postgresql"
test -s "$pgroot/bin/pg_config"
testroot="$work/merged/postgresql"
mv "$pgroot" "$testroot"
tar -xzf "$core_archives/$core_name" -C "$work/compiled-prefix"
prefix_target="$work/compiled-prefix/postgresql"
payload="$work/extension/pg_jsonschema"
test -d "$payload"
python3 - "$payload" "$testroot" "$module_filename" <<'PY'
import pathlib
import sys

payload, target = map(pathlib.Path, sys.argv[1:3])
module = sys.argv[3]
files = {path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file()}
required = {f"lib/{module}", "share/extension/pg_jsonschema.control",
            "LICENSES/pg_jsonschema.txt", "LICENSES/pg_jsonschema-cargo-license-inventory.json"}
if not required <= files or sum(path.startswith("lib/") for path in files) != 1:
    raise SystemExit("pg_jsonschema archive payload is incomplete or has extra native code")
for source in payload.rglob("*"):
    destination = target / source.relative_to(payload)
    if destination.exists() or destination.is_symlink():
        raise SystemExit(f"pg_jsonschema archive collides with PostgreSQL core: {source.relative_to(payload)}")
for source in payload.rglob("*"):
    destination = target / source.relative_to(payload)
    if source.is_dir(): destination.mkdir(parents=True, exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
PY
cp "$payload/LICENSES/pg_jsonschema-cargo-license-inventory.json" "$output/cargo-license-inventory.json"

python3 - "$testroot" "$pg_version" "$architecture" "$core_build_id" "$core_revision" <<'PY'
import json, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
version, architecture, build_id, revision = sys.argv[2:]
manifest = json.loads((root / "manifest.json").read_text())
expected = {"component": "postgresql", "version": version, "postgresql_version": version,
            "platform": "macos", "architecture": architecture, "build_id": build_id,
            "source_revision": revision}
for key, value in expected.items():
    if manifest.get(key) != value: raise SystemExit(f"PostgreSQL core manifest mismatch for {key}")
header = (root / "include/server/pg_config.h").read_text()
match = re.search(r'#define CONFIGURE_ARGS "[^\n]*?--prefix=([^\']+)', header)
if not match: raise SystemExit("cannot read PostgreSQL archive installation prefix")
prefix = pathlib.Path(match.group(1))
if not re.fullmatch(r"/Users/runner/work/_temp/pg-macos-pilot\.[A-Za-z0-9]+/install/postgresql", str(prefix)):
    raise SystemExit(f"unexpected PostgreSQL archive installation prefix: {prefix}")
print(prefix)
PY
prefix=$(python3 - "$testroot" <<'PY'
import pathlib, re, sys
header = (pathlib.Path(sys.argv[1]) / "include/server/pg_config.h").read_text()
print(re.search(r'#define CONFIGURE_ARGS "[^\n]*?--prefix=([^\']+)', header).group(1))
PY
)
if [[ -e $prefix || -L $prefix ]]; then echo "Refusing to replace existing PostgreSQL prefix path: $prefix" >&2; exit 1; fi
mkdir -p "$(dirname "$prefix")"
ln -s "$prefix_target" "$prefix"
prefix_link=$prefix
prefix_link_created=true
python3 "$repo/scripts/macos/static_analysis.py" "$testroot" "$architecture" \
  --archive "$core_archives/$core_name" --archive "$extension_archives/$extension_name" \
  --report "$output/static-analysis.json"

mkdir -p "$work/data"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
macos_hide_compiled_prefix "$prefix" "$prefix_target"
test ! -e "$prefix" && test ! -L "$prefix"
"$testroot/bin/initdb" -D "$work/data" --encoding=UTF8 --locale=C --no-instructions >/dev/null
"$testroot/bin/pg_ctl" -D "$work/data" -l "$work/server.log" -o "-k $work/socket -p 55432 -h ''" -w start
server_data="$work/data"
"$testroot/bin/psql" -X -A -t -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 \
  -d postgres -f "$repo/scripts/pg_jsonschema/probe.sql" | tee "$output/probe-output.txt"
grep -Fxq 'pg_jsonschema|0.3.4' "$output/probe-output.txt"
"$testroot/bin/pg_ctl" -D "$work/data" -m fast -w stop
server_data=
macos_restore_compiled_prefix
prefix_link_created=true
if [[ $extension_archives != "$output" ]]; then
  cp "$extension_archives/build-evidence.txt" "$output/build-evidence.txt"
fi
{
  echo "verification_macos_version=$(sw_vers -productVersion)"
  echo "verification_architecture=$(uname -m)"
  "$testroot/bin/pg_config" --version
} >> "$output/build-evidence.txt"
echo "PASS: pg_jsonschema $extension_version final archives relocated, inspected and exercised with PostgreSQL $pg_version on macOS $architecture"
