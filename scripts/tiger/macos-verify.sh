#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-verify.sh CORE_DIRECTORY POSTGIS_ARCHIVE TIGER_ARCHIVE OUTPUT_DIRECTORY PG_VERSION ARCHITECTURE}
postgis_archive=${2:?usage: macos-verify.sh CORE_DIRECTORY POSTGIS_ARCHIVE TIGER_ARCHIVE OUTPUT_DIRECTORY PG_VERSION ARCHITECTURE}
tiger_archive=${3:?usage: macos-verify.sh CORE_DIRECTORY POSTGIS_ARCHIVE TIGER_ARCHIVE OUTPUT_DIRECTORY PG_VERSION ARCHITECTURE}
output=${4:?usage: macos-verify.sh CORE_DIRECTORY POSTGIS_ARCHIVE TIGER_ARCHIVE OUTPUT_DIRECTORY PG_VERSION ARCHITECTURE}
pg_version=${5:?usage: macos-verify.sh CORE_DIRECTORY POSTGIS_ARCHIVE TIGER_ARCHIVE OUTPUT_DIRECTORY PG_VERSION ARCHITECTURE}
architecture=${6:?usage: macos-verify.sh CORE_DIRECTORY POSTGIS_ARCHIVE TIGER_ARCHIVE OUTPUT_DIRECTORY PG_VERSION ARCHITECTURE}
case "$pg_version" in 16.*|17.*|18.*) ;; *) echo "Unsupported PostgreSQL version: $pg_version" >&2; exit 2 ;; esac
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported macOS architecture: $architecture" >&2; exit 2 ;; esac
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then echo "TIGER verifier requires native macOS $architecture" >&2; exit 1; fi
if [[ $(id -u) == 0 ]]; then echo 'Verification must run as an ordinary user' >&2; exit 1; fi
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core_archives=$(cd "$core_archives" && pwd)
postgis_archive=$(cd "$(dirname "$postgis_archive")" && pwd)/$(basename "$postgis_archive")
tiger_archive=$(cd "$(dirname "$tiger_archive")" && pwd)/$(basename "$tiger_archive")
mkdir -p "$output"
output=$(cd "$output" && pwd)
core_name="postgresql-${pg_version}-macos-${architecture}.tar.gz"
postgis_name="postgis-3.6.4-postgresql-${pg_version}-macos-${architecture}.tar.gz"
tiger_name="postgis_tiger_geocoder-2025.2-postgresql-${pg_version}-macos-${architecture}.tar.gz"
test "$(basename "$postgis_archive")" = "$postgis_name"
test "$(basename "$tiger_archive")" = "$tiger_name"
for archive in "$core_archives/$core_name" "$postgis_archive" "$tiger_archive"; do
  test -s "$archive" && test -s "$archive.sha256"
  (cd "$(dirname "$archive")" && shasum -a 256 -c "$(basename "$archive").sha256")
done
core_sha256=$(shasum -a 256 "$core_archives/$core_name" | awk '{print $1}')
python3 "$repo/tools/license_pointer.py" verify "$core_archives/$core_name" postgresql
python3 "$repo/tools/license_pointer.py" verify "$postgis_archive" postgis
python3 "$repo/tools/license_pointer.py" verify "$tiger_archive" postgis_tiger_geocoder
python3 - "$postgis_archive" "$tiger_archive" "$pg_version" "$architecture" "$core_name" "$core_sha256" <<'PY'
import json, sys, tarfile
postgis, tiger, version, architecture, core_name, core_sha = sys.argv[1:]
with tarfile.open(postgis, 'r:gz') as stream:
    pm = json.load(stream.extractfile('metadata.json'))
with tarfile.open(tiger, 'r:gz') as stream:
    tm = json.load(stream.extractfile('metadata.json'))
expected = {'postgresql_version':version, 'platform':'macos', 'architecture':architecture}
if any(pm.get(key) != value for key,value in expected.items()) or pm.get('project') != 'postgis' or pm.get('version') != '3.6.4':
    raise SystemExit('PostGIS prerequisite metadata mismatch')
if pm.get('core_archive') != {'basename':core_name,'sha256':core_sha}:
    raise SystemExit('PostGIS prerequisite refers to different core archive bytes')
if any(tm.get(key) != value for key,value in expected.items()) or tm.get('project') != 'postgis_tiger_geocoder' or tm.get('version') != '2025.2':
    raise SystemExit('TIGER metadata mismatch')
if tm.get('source') != {'url':'https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-2025.2.tar.gz',
                        'sha256':'c33cfbfb40785db8754a36be66060e8d023773e7e1be8fb8a622bb3c48db9f54'}:
    raise SystemExit('TIGER metadata source mismatch')
PY

work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/tiger-macos-verify.XXXXXX")
data_dir=; pg_ctl=; prefix_link_created=false
prefix_link=
cleanup() {
  [[ -z "$pg_ctl" || -z "$data_dir" ]] || "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
  source "$repo/scripts/macos/core-prefix.sh"; macos_remove_core_prefix
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/assembled" "$work/postgis" "$work/tiger" "$work/socket"
tar -xzf "$core_archives/$core_name" -C "$work/assembled"
tar -xzf "$postgis_archive" -C "$work/postgis"
tar -xzf "$tiger_archive" -C "$work/tiger"
pgroot="$work/assembled/postgresql"
postgis_root="$work/postgis/postgis"
tiger_root="$work/tiger/postgis_tiger_geocoder"
python3 - "$work/postgis" "$work/tiger" "$pgroot" <<'PY'
from pathlib import Path
import sys
archive_roots = ((Path(sys.argv[1]),'postgis'),(Path(sys.argv[2]),'postgis_tiger_geocoder'))
core = Path(sys.argv[3])
occupied = set()
for archive_root, component in archive_roots:
    if {p.name for p in archive_root.iterdir()} != {component,'metadata.json'}:
        raise SystemExit(f'{component} archive contains unexpected top-level entries')
    for source in (archive_root/component).rglob('*'):
        if not source.is_file() and not source.is_symlink(): continue
        relative = source.relative_to(archive_root/component)
        destination=core/relative
        if relative in occupied:
            raise SystemExit(f'{component} payload collides with the other extension archive: {relative}')
        if destination.exists() or destination.is_symlink():
            raise SystemExit(f'{component} payload collides with assembled PostgreSQL: {relative}')
        occupied.add(relative)
PY
cp -a "$postgis_root/." "$pgroot/"
cp -a "$tiger_root/." "$pgroot/"
manifest=$(python3 - "$pgroot/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1])); print('\t'.join((m['build_id'],m['source_revision'])))
PY
)
IFS=$'\t' read -r core_build_id core_revision <<< "$manifest"
source "$repo/scripts/macos/core-prefix.sh"
prefix=$(macos_core_prefix_from_archive "$pgroot" "$pg_version" "$architecture" "$core_build_id" "$core_revision")
macos_restore_core_prefix "$prefix" "$pgroot"
test -s "$pgroot/share/extension/postgis_tiger_geocoder.control"
test -s "$pgroot/share/extension/postgis_tiger_geocoder--2025.2.sql"
if find "$tiger_root" -type f \( -name '*.dylib' -o -name '*.so' -o -name '*.dll' \) | grep -q .; then echo 'TIGER SQL-only archive contains a native library' >&2; exit 1; fi
python3 "$repo/scripts/macos/static_analysis.py" "$pgroot" "$architecture" \
  --archive "$core_archives/$core_name" --archive "$postgis_archive" --archive "$tiger_archive" \
  --report "$output/static-analysis.json"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
export PROJ_DATA="$pgroot/share/proj" PROJ_LIB="$pgroot/share/proj" GDAL_DATA="$pgroot/share/gdal"
data_dir="$work/data"; pg_ctl="$pgroot/bin/pg_ctl"
"$pgroot/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >"$output/initdb.log" 2>&1
"$pg_ctl" -D "$data_dir" -l "$output/postgresql.log" -o "-k $work/socket -p 55435 -h ''" -w start
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55435 -d postgres -f "$repo/scripts/tiger/probe.sql" | tee "$output/probe-output.txt"
"$pg_ctl" -D "$data_dir" -m fast -w stop; data_dir=; pg_ctl=
echo "PASS: relocated PostGIS and separate TIGER archives exercised with PostgreSQL $pg_version on macOS $architecture"
