#!/usr/bin/env bash
set -euo pipefail

core_archive=${1:?usage: macos-verify-selected.sh CORE_ARCHIVE EXTENSION_ARCHIVE PG_VERSION ARCHITECTURE OUTPUT_DIR}
extension_archive=${2:?extension archive required}
pg_version=${3:?PostgreSQL version required}
architecture=${4:?architecture required}
output=${5:?output directory required}
repo=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "Verification requires fresh native macOS $architecture" >&2; exit 1
fi
mkdir -p "$output"
for archive in "$core_archive" "$extension_archive"; do
  test -s "$archive" && test -s "$archive.sha256"
  (cd "$(dirname "$archive")" && shasum -a 256 -c "$(basename "$archive").sha256")
done
work=$(mktemp -d /tmp/address-standardizer-macos-verify.XXXXXX)
cleanup() { [[ -z ${pg_ctl:-} || -z ${data_dir:-} ]] || "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$work/assembled" "$work/extract" "$work/relocated" "$work/socket"
tar -xzf "$core_archive" -C "$work/assembled"
tar -xzf "$extension_archive" -C "$work/extract"
python3 - "$work/assembled/postgresql" "$work/extract/address_standardizer" "$work/extract/metadata.json" "$pg_version" "$architecture" <<'PY'
import json, pathlib, sys
core, extension, metadata = map(pathlib.Path, sys.argv[1:4])
pg, arch = sys.argv[4:]
meta=json.loads(metadata.read_text())
expected=("Address Standardizer","3.7.0",pg,"macos",arch,["address_standardizer","address_standardizer_data_us"])
actual=(meta.get("project"),meta.get("version"),meta.get("postgresql_version"),meta.get("platform"),meta.get("architecture"),meta.get("sql_names"))
if actual != expected: raise SystemExit(f"extension metadata mismatch: {actual!r}")
for source in extension.rglob("*"):
    destination=core/source.relative_to(extension)
    if destination.exists() or destination.is_symlink():
        if source.is_dir() and destination.is_dir() and not source.is_symlink() and not destination.is_symlink(): continue
        raise SystemExit(f"Address Standardizer payload collision: {source.relative_to(extension)}")
for required in ("LICENSES/license-inventory.json", "LICENSES/Address-Standardizer.txt", "LICENSES/PCRE2.txt", "share/extension/address_standardizer.control", "share/extension/address_standardizer_data_us.control", "lib/postgresql/address_standardizer.dylib"):
    if not (extension/required).is_file(): raise SystemExit(f"archive is missing {required}")
PY
ditto "$work/extract/address_standardizer" "$work/assembled/postgresql"
python3 "$repo/scripts/macos/static_analysis.py" "$work/assembled/postgresql" "$architecture" \
  --archive "$core_archive" --archive "$extension_archive" --report "$output/static-analysis.json"
mv "$work/assembled/postgresql" "$work/relocated/postgresql"
root="$work/relocated/postgresql"
test "$("$root/bin/pg_config" --version)" = "PostgreSQL $pg_version"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
data_dir="$work/data"; pg_ctl="$root/bin/pg_ctl"
"$root/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >/dev/null
"$pg_ctl" -D "$data_dir" -l "$work/server.log" -o "-k $work/socket -p 55441 -h ''" -w start
"$root/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55441 -d postgres \
  -f "$repo/scripts/address_standardizer/probe.sql" | tee "$output/probe-output.txt"
"$pg_ctl" -D "$data_dir" -m fast -w stop
pg_ctl=; data_dir=
echo "PASS: final Address Standardizer archives verified on fresh macOS $architecture runner"
