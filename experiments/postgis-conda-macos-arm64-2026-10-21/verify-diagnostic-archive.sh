#!/usr/bin/env bash
set -euo pipefail

core_dir=${1:?usage: verify-diagnostic-archive.sh CORE_DIR EXTENSION_DIR OUTPUT}
extension_dir=${2:?extension artifact directory required}
output=${3:?output directory required}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
mkdir -p "$output"; output=$(cd "$output" && pwd)
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo 'Verification requires fresh native macOS arm64' >&2; exit 1; }
core_archive="$core_dir/postgresql-18.6-macos-arm64.tar.gz"
extension="$extension_dir/postgis-3.6.4-postgresql-18.6-macos-arm64.tar.gz"
for archive in "$core_archive" "$extension"; do
  test -s "$archive"
  (cd "$(dirname "$archive")" && shasum -a 256 -c "$(basename "$archive").sha256")
done
work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/postgis-conda-verify.XXXXXX")
data=; socket="$work/socket"; pgctl=
cleanup() { [[ -z "$data" || -z "$pgctl" ]] || "$pgctl" -D "$data" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$work/assembled" "$work/extract" "$socket"
tar -xzf "$core_archive" -C "$work/assembled"
tar -xzf "$extension" -C "$work/extract"
pgroot="$work/assembled/postgresql"; extension_root="$work/extract/postgis"
python3 - "$core_archive" "$extension" "$extension_root" "$pgroot" <<'PY'
import hashlib,json,pathlib,sys,tarfile
core_archive,extension,root,pgroot=map(pathlib.Path,sys.argv[1:])
with tarfile.open(extension,'r:gz') as stream:
    metadata=json.load(stream.extractfile('metadata.json'))
expected={'project':'postgis','version':'3.6.4','sql_names':['postgis','postgis_raster','postgis_sfcgal','postgis_topology'],'postgresql_version':'18.6','platform':'macos','architecture':'arm64','core_archive':{'basename':core_archive.name,'sha256':hashlib.sha256(core_archive.read_bytes()).hexdigest()}}
if any(metadata.get(key)!=value for key,value in expected.items()): raise SystemExit('archive metadata identity mismatch')
if not metadata.get('build_id','').startswith('github-') or len(metadata.get('source_revision',''))!=40: raise SystemExit('missing build provenance')
if hashlib.sha256(extension.read_bytes()).hexdigest()!=pathlib.Path(str(extension)+'.sha256').read_text().split()[0]: raise SystemExit('extension checksum mismatch')
inventory=json.loads((root/'LICENSES/postgis-inventory.json').read_text())
if not inventory.get('components') or any(item.get('redistribution_review',{}).get('status')!='pending' for item in inventory['components']): raise SystemExit('diagnostic inventory must remain pending')
core_inventory=json.loads((pgroot/'LICENSES/inventory.json').read_text())
for item in inventory.get('reused_core_dependencies',[]):
    path=pgroot/'lib'/item['library']
    owner=next((value for value in core_inventory['components'] if item['library'] in value.get('libraries',[])),None)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item.get('sha256') or not owner or owner.get('redistribution_review',{}).get('status')!='resolved': raise SystemExit(f"invalid reused core dependency: {item.get('library')}")
    if item.get('license_file')!='LICENSES/'+owner.get('license_file'): raise SystemExit(f"core licence reference mismatch: {item.get('library')}")
mapped=set()
for item in inventory['components']:
    license_path=root/item['license_file']
    if not license_path.is_file() or not license_path.stat().st_size: raise SystemExit(f"missing declaration or notice: {item['license_file']}")
    for path in item['payload_paths']:
        candidate=root/path
        if not candidate.exists(): raise SystemExit(f'missing mapped payload: {path}')
        members={p.relative_to(root).as_posix() for p in candidate.rglob('*') if p.is_file()} if candidate.is_dir() else {path}
        if mapped.intersection(members): raise SystemExit(f'duplicate payload mapping: {path}')
        mapped.update(members)
actual={p.relative_to(root).as_posix() for top in ('lib','share') for p in (root/top).rglob('*') if p.is_file()}
if actual!=mapped: raise SystemExit(f'payload mapping mismatch: missing={sorted(actual-mapped)} extra={sorted(mapped-actual)}')
for name in expected['sql_names']:
    if not (root/f'share/extension/{name}.control').is_file(): raise SystemExit(f'missing SQL extension {name}')
for source in root.rglob('*'):
    if not source.is_file(): continue
    destination=pgroot/source.relative_to(root)
    if destination.exists() or destination.is_symlink(): raise SystemExit(f'core collision at {source.relative_to(root)}')
PY
cp -a "$extension_root/." "$pgroot/"
python3 "$repo/scripts/macos/static_analysis.py" "$pgroot" arm64 --archive "$core_archive" --archive "$extension" --report "$output/static-analysis.json"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
export PROJ_DATA="$pgroot/share/proj" PROJ_LIB="$pgroot/share/proj" GDAL_DATA="$pgroot/share/gdal"
data="$work/data"; pgctl="$pgroot/bin/pg_ctl"
"$pgroot/bin/initdb" -D "$data" --encoding=UTF8 --locale=C --no-instructions >"$output/initdb.log" 2>&1
"$pgctl" -D "$data" -l "$output/postgres.log" -o "-k $socket -p 55442 -h ''" -w start
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$socket" -p 55442 -d postgres -f "$repo/scripts/postgis/probe.sql" | tee "$output/probe-output.txt"
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$socket" -p 55442 -d postgres <<'SQL' | tee "$output/raster-probe.txt"
SET postgis.gdal_enabled_drivers = 'GTiff PNG JPEG';
DO $$ DECLARE r raster; BEGIN
  IF (SELECT count(*) FROM ST_GDALDrivers() WHERE short_name IN ('GTiff','PNG','JPEG')) <> 3 THEN RAISE EXCEPTION 'minimal GDAL drivers unavailable'; END IF;
  r:=ST_AddBand(ST_MakeEmptyRaster(2,2,0,2,1,-1,0,0,4326),'8BUI'::text,128::double precision,0::double precision);
  IF octet_length(ST_AsTIFF(r))<=0 OR octet_length(ST_AsPNG(r))<=0 OR octet_length(ST_AsJPEG(r))<=0 THEN RAISE EXCEPTION 'raster serialization failed'; END IF;
END $$;
SQL
"$pgctl" -D "$data" -m fast -w stop; data=; pgctl=
echo 'PASS: diagnostic PostGIS archive passed fresh-runner relocation, static and SQL checks; licence inventory remains pending'
