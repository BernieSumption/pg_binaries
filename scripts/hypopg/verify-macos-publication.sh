#!/usr/bin/env bash
set -euo pipefail

phase=${1:?usage: verify-macos-publication.sh PHASE CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
core_archives=${2:?usage: verify-macos-publication.sh PHASE CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
extension_archives=${3:?usage: verify-macos-publication.sh PHASE CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
output=${4:?usage: verify-macos-publication.sh PHASE CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
target_config=${5:?usage: verify-macos-publication.sh PHASE CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
case "$phase" in static-analysis|archive-suite) ;; *) echo "Unknown verification phase: $phase" >&2; exit 2 ;; esac

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
target_values=$(PYTHONPATH="$repo/tools" python3 - "$target_config" <<'PY'
import sys
from hypopg_macos_target import load_target_config

print("\t".join(load_target_config(sys.argv[1]).shell_values()))
PY
)
IFS=$'\t' read -r pg_version architecture platform profile_id core_name core_run_id \
  core_sha256 core_build_id core_source_revision source_url source_sha256 <<< "$target_values"
extension_name="hypopg-1.4.3-postgresql-${pg_version}-${platform}.tar.gz"
core_archives=$(cd "$core_archives" && pwd)
extension_archives=$(cd "$extension_archives" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)

if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This verifier requires native macOS $architecture" >&2
  exit 1
fi
if [[ $(id -u) == 0 ]]; then
  echo "Verification must run as an ordinary user" >&2
  exit 1
fi
test -s "$core_archives/$core_name" && test -s "$core_archives/$core_name.sha256"
test -s "$extension_archives/$extension_name" && test -s "$extension_archives/$extension_name.sha256"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_archives" && shasum -a 256 -c -)
(cd "$extension_archives" && shasum -a 256 -c "$extension_name.sha256")

python3 - "$extension_archives/$extension_name" "$extension_name" "$pg_version" "$architecture" \
  "$core_name" "$core_sha256" "$source_url" "$source_sha256" <<'PY'
import json
import pathlib
import sys
import tarfile

archive_path, _extension_name, pg_version, architecture, core_name, core_sha, source_url, source_sha = sys.argv[1:]
with tarfile.open(archive_path, "r:gz") as archive:
    names = [member.name for member in archive.getmembers()]
    if any(name.startswith("/") or ".." in pathlib.PurePosixPath(name).parts for name in names):
        raise SystemExit("extension archive contains an unsafe path")
    if not names or any(name.split("/", 1)[0] not in {"hypopg", "metadata.json"} for name in names):
        raise SystemExit("extension archive has an unexpected top-level entry")
    member = archive.getmember("metadata.json")
    if not member.isfile() or member.size > 1024 * 1024:
        raise SystemExit("extension archive requires bounded metadata.json")
    metadata = json.load(archive.extractfile(member))
expected = {
    "project": "hypopg", "version": "1.4.3", "sql_names": ["hypopg"],
    "postgresql_version": pg_version, "platform": "macos", "architecture": architecture,
    "source": {"url": source_url, "sha256": source_sha},
    "core_archive": {"basename": core_name, "sha256": core_sha},
}
if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in expected.items()):
    raise SystemExit("HypoPG metadata does not match the pinned target and core archive")
PY

work=$(mktemp -d "$RUNNER_TEMP/hypopg-verify.XXXXXX")
data_dir=
pg_ctl=
cleanup() {
  if [[ -n "$pg_ctl" && -n "$data_dir" ]]; then
    "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/unpacked-core" "$work/unpacked-extension" "$work/moved" "$work/socket"
tar -xzf "$core_archives/$core_name" -C "$work/unpacked-core"
tar -xzf "$extension_archives/$extension_name" -C "$work/unpacked-extension"
pgroot="$work/unpacked-core/postgresql"
extroot="$work/unpacked-extension/hypopg"
test -d "$pgroot" && test -d "$extroot"
modules=("$extroot/lib/hypopg.so" "$extroot/lib/hypopg.dylib")
found_modules=()
for module in "${modules[@]}"; do
  [[ -s "$module" ]] && found_modules+=("$module")
done
if [[ ${#found_modules[@]} -ne 1 ]]; then
  echo "Expected one HypoPG module (.so or .dylib) in $extroot/lib" >&2
  exit 1
fi

# Follow the documented installation process: unpack each archive and copy the
# extension payload into the core prefix, merging directories and rejecting file collisions.
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then
      continue
    fi
    echo "HypoPG payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv "$pgroot" "$work/moved/postgresql"
pgroot="$work/moved/postgresql"
cp -a "$extroot/." "$pgroot/"
test ! -e "$work/unpacked-core/postgresql"
test ! -L "$work/unpacked-core/postgresql"

if [[ "$phase" == static-analysis ]]; then
  python3 "$repo/scripts/macos/static_analysis.py" "$pgroot" "$architecture" \
    --archive "$core_archives/$core_name" --archive "$extension_archives/$extension_name" \
    --report "$output/static-analysis.json"
  exit $?
fi

data_dir="$work/data"
pg_ctl="$pgroot/bin/pg_ctl"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
"$pgroot/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >"$output/initdb.log" 2>&1
"$pg_ctl" -D "$data_dir" -l "$output/postgresql.log" -o "-k $work/socket -p 55432 -h ''" -w start
"$pgroot/bin/psql" -X -A -t -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 \
  -v expected_pg_major="${pg_version%%.*}" -d postgres \
  -f "$repo/scripts/hypopg/macos-probe.sql" | tee "$output/probe-output.txt"
grep -Eq '^t$' "$output/probe-output.txt"
grep -Eq '^Index Scan using .*btree_hypo_probe_id' "$output/probe-output.txt"
grep -Eq '^0$' "$output/probe-output.txt"
"$pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=
pg_ctl=
echo "PASS: relocated HypoPG 1.4.3 archive exercised with PostgreSQL $pg_version on fresh macOS $architecture runner"
