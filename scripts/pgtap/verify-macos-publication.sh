#!/usr/bin/env bash
set -euo pipefail

phase=${1:?usage: verify-macos-publication.sh PHASE CORE_ARCHIVE_DIRECTORY PGTAP_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
core_archives=${2:?usage: verify-macos-publication.sh PHASE CORE_ARCHIVE_DIRECTORY PGTAP_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
pgtap_archives=${3:?usage: verify-macos-publication.sh PHASE CORE_ARCHIVE_DIRECTORY PGTAP_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
output=${4:?usage: verify-macos-publication.sh PHASE CORE_ARCHIVE_DIRECTORY PGTAP_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
target_config=${5:?usage: verify-macos-publication.sh PHASE CORE_ARCHIVE_DIRECTORY PGTAP_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
case "$phase" in static-analysis|archive-suite) ;; *) echo "Unknown verification phase: $phase" >&2; exit 2 ;; esac

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
target_values=$(PYTHONPATH="$repo/tools" python3 - "$target_config" <<'PY'
import sys
from pgtap_macos_target import load_target_config

print("\t".join(load_target_config(sys.argv[1]).shell_values()))
PY
)
IFS=$'\t' read -r pg_version version architecture platform profile_id core_name core_run_id \
  core_sha256 core_build_id core_source_revision source_url source_sha256 <<< "$target_values"
extension_name="pgtap-${version}-postgresql-${pg_version}-${platform}.tar.gz"
python3 "$repo/tools/license_pointer.py" verify "$pgtap_archives/$extension_name" pgtap
core_archives=$(cd "$core_archives" && pwd)
pgtap_archives=$(cd "$pgtap_archives" && pwd)
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
test -s "$pgtap_archives/$extension_name" && test -s "$pgtap_archives/$extension_name.sha256"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_archives" && shasum -a 256 -c -)
(cd "$pgtap_archives" && shasum -a 256 -c "$extension_name.sha256")
python3 "$repo/tools/check_extension_redistribution.py" "$pgtap_archives/$extension_name"

python3 - "$core_archives/$core_name" "$pgtap_archives/$extension_name" "$pg_version" \
  "$version" "$architecture" "$platform" "$core_name" "$core_sha256" "$core_build_id" \
  "$core_source_revision" "$source_url" "$source_sha256" <<'PY'
import json
import pathlib
import sys
import tarfile

core_path, ext_path, pg_version, version, architecture, platform, core_name, core_sha, build_id, source_revision, source_url, source_sha = sys.argv[1:]
with tarfile.open(core_path, "r:gz") as archive:
    manifest_member = archive.getmember("postgresql/manifest.json")
    if not manifest_member.isfile() or manifest_member.size > 1024 * 1024:
        raise SystemExit("core archive requires bounded postgresql/manifest.json")
    manifest = json.load(archive.extractfile(manifest_member))
with tarfile.open(ext_path, "r:gz") as archive:
    members = archive.getmembers()
    names = [member.name for member in members]
    if any(name.startswith("/") or ".." in pathlib.PurePosixPath(name).parts for name in names):
        raise SystemExit("pgTAP archive contains an unsafe path")
    if not names or any(name.split("/", 1)[0] not in {"pgtap", "metadata.json"} for name in names):
        raise SystemExit("pgTAP archive has an unexpected top-level entry")
    metadata_member = archive.getmember("metadata.json")
    if not metadata_member.isfile() or metadata_member.size > 1024 * 1024:
        raise SystemExit("pgTAP archive requires bounded metadata.json")
    metadata = json.load(archive.extractfile(metadata_member))
    payload = {member.name for member in members if member.isfile()}
expected = {
    "project": "pgtap", "version": version, "sql_names": ["pgtap"],
    "postgresql_version": pg_version, "platform": "macos", "architecture": architecture,
    "source": {"url": source_url, "sha256": source_sha},
    "core_archive": {"basename": core_name, "sha256": core_sha},
}
if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in expected.items()):
    raise SystemExit("pgTAP metadata does not match the pinned target and core archive")
expected_manifest = {"component": "postgresql", "version": pg_version,
                     "postgresql_version": pg_version, "platform": "macos",
                     "architecture": architecture, "build_id": build_id,
                     "source_revision": source_revision}
if not isinstance(manifest, dict) or any(manifest.get(key) != value for key, value in expected_manifest.items()):
    raise SystemExit("core archive manifest does not match the pinned target")
required = {
    "pgtap/share/extension/pgtap.control",
    f"pgtap/share/extension/pgtap--{version}.sql",
    f"pgtap/share/extension/pgtap-core--{version}.sql",
    f"pgtap/share/extension/pgtap-schema--{version}.sql",
    f"pgtap/share/extension/pgtap--1.3.3--{version}.sql",
    "pgtap/share/doc/extension/pgtap.mmd",
}
if not required.issubset(payload):
    raise SystemExit("pgTAP archive is missing required SQL or documentation files")
if any(pathlib.PurePosixPath(name).suffix in {".so", ".dylib", ".dll"} for name in payload):
    raise SystemExit("pgTAP SQL-only archive unexpectedly contains a native library")
PY

work_parent=${RUNNER_TEMP:-${TMPDIR:-/tmp}}
work=$(mktemp -d "$work_parent/pgtap-verify.XXXXXX")
data_dir=
pg_ctl=
cleanup() {
  if [[ -n "$pg_ctl" && -n "$data_dir" ]]; then
    "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/unpacked-core" "$work/unpacked-pgtap" "$work/moved" "$work/socket"
tar -xzf "$core_archives/$core_name" -C "$work/unpacked-core"
tar -xzf "$pgtap_archives/$extension_name" -C "$work/unpacked-pgtap"
pgroot="$work/unpacked-core/postgresql"
extroot="$work/unpacked-pgtap/pgtap"
test -d "$pgroot" && test -d "$extroot"

while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then
      continue
    fi
    echo "pgTAP payload collision: $relative" >&2
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
    --archive "$core_archives/$core_name" --archive "$pgtap_archives/$extension_name" \
    --report "$output/static-analysis.json"
  exit $?
fi

data_dir="$work/data"
pg_ctl="$pgroot/bin/pg_ctl"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
"$pgroot/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >"$output/initdb.log" 2>&1
"$pg_ctl" -D "$data_dir" -l "$output/postgresql.log" -o "-k $work/socket -p 55432 -h ''" -w start
"$pgroot/bin/psql" -X -A -t -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 \
  -d postgres -f "$repo/scripts/pgtap/probe.sql" | tee "$output/probe-output.txt"
grep -Fxq '1..4' "$output/probe-output.txt"
test "$(grep -Ec '^ok [1-4]( -|$)' "$output/probe-output.txt")" -eq 4
"$pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=
pg_ctl=
echo "PASS: relocated pgTAP $version archive exercised with PostgreSQL $pg_version on fresh macOS $architecture runner"
