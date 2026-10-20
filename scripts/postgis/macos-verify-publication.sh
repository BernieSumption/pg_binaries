#!/usr/bin/env bash
set -euo pipefail
core_archive=${1:?usage: macos-verify-publication.sh CORE_ARCHIVE EXTENSION_DIR OUTPUT}
archives=${2:?extension archive directory required}
output=${3:?output directory required}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
mkdir -p "$output"; output=$(cd "$output" && pwd)
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo 'Verification requires fresh native macOS arm64' >&2; exit 1; }
extension="$archives/postgis-3.6.4-postgresql-18.6-macos-arm64.tar.gz"
for archive in "$core_archive" "$extension"; do test -s "$archive"; (cd "$(dirname "$archive")" && shasum -a 256 -c "$(basename "$archive").sha256"); done
core_sha=$(shasum -a 256 "$core_archive" | awk '{print $1}')
ext_sha=$(shasum -a 256 "$extension" | awk '{print $1}')
work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/postgis-macos-verify.XXXXXX")
pg_ctl=; data_dir=
cleanup() { [[ -z "$pg_ctl" || -z "$data_dir" ]] || "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$work/assembled" "$work/extract" "$work/socket"
tar -xzf "$core_archive" -C "$work/assembled"
tar -xzf "$extension" -C "$work/extract"
pgroot="$work/assembled/postgresql"; extroot="$work/extract/postgis"
python3 - "$extroot" "$extension" "$core_archive" "$core_sha" "$ext_sha" "$pgroot" <<'PY'
import hashlib,json,pathlib,sys,tarfile
ext,archive,core=map(pathlib.Path,sys.argv[1:4]); core_sha,ext_sha=sys.argv[4:6]; core_root=pathlib.Path(sys.argv[6])
with tarfile.open(archive,'r:gz') as stream:
    metadata=json.load(stream.extractfile('metadata.json'))
expected={'project':'postgis','version':'3.6.4','sql_names':['postgis','postgis_raster','postgis_sfcgal','postgis_topology'],'postgresql_version':'18.6','platform':'macos','architecture':'arm64','core_archive':{'basename':core.name,'sha256':core_sha}}
if any(metadata.get(key)!=value for key,value in expected.items()): raise SystemExit('PostGIS archive metadata identity mismatch')
if not metadata.get('build_id','').startswith('github-') or len(metadata.get('source_revision',''))!=40: raise SystemExit('missing PostGIS build provenance')
if hashlib.sha256(archive.read_bytes()).hexdigest()!=ext_sha: raise SystemExit('extension archive bytes changed')
inventory=json.loads((ext/'LICENSES/postgis-inventory.json').read_text())
if inventory.get('schema_version')!=1 or not inventory.get('components'): raise SystemExit('missing PostGIS licence inventory')
core_inventory=json.loads((core_root/'LICENSES/inventory.json').read_text())
for item in inventory.get('reused_core_dependencies',[]):
    library=item.get('library'); path=core_root/'lib'/library
    owner=next((value for value in core_inventory['components'] if library in value.get('libraries',[])),None)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=item.get('sha256') or not owner or owner.get('redistribution_review',{}).get('status')!='resolved':
        raise SystemExit(f'invalid checked-core dependency reuse record: {library}')
    if item.get('license_file')!='LICENSES/'+owner.get('license_file'): raise SystemExit(f'core licence reference mismatch: {library}')
mapped=set()
for component in inventory['components']:
    if component.get('redistribution_review',{}).get('status')!='resolved': raise SystemExit(f"unresolved redistribution record: {component.get('component')}")
    license_file=ext/component.get('license_file','')
    if not license_file.is_file() or not license_file.stat().st_size: raise SystemExit(f'missing licence text: {license_file}')
    for relative in component.get('additional_license_files',[]):
        if not (ext/relative).is_file(): raise SystemExit(f'missing additional licence record: {relative}')
    for relative in component.get('payload_paths',[]):
        source=ext/relative
        if not source.exists(): raise SystemExit(f'missing mapped payload: {relative}')
        entries=({p.relative_to(ext).as_posix() for p in source.rglob('*') if p.is_file()} if source.is_dir() else {relative})
        if mapped.intersection(entries): raise SystemExit(f'duplicate mapped payload: {relative}')
        mapped.update(entries)
actual={p.relative_to(ext).as_posix() for top in ('lib','share') for p in (ext/top).rglob('*') if p.is_file()}
if actual!=mapped: raise SystemExit(f"licence payload mapping mismatch: missing={sorted(actual-mapped)} extra={sorted(mapped-actual)}")
for name in ('postgis','postgis_raster','postgis_sfcgal','postgis_topology'):
    if not (ext/f'share/extension/{name}.control').is_file(): raise SystemExit(f'missing {name} control')
PY
python3 - "$pgroot" "$extroot" <<'PY'
from pathlib import Path
import sys
core,extension=map(Path,sys.argv[1:])
for source in extension.rglob('*'):
    if not source.is_file(): continue
    destination=core/source.relative_to(extension)
    if destination.exists() or destination.is_symlink(): raise SystemExit(f'PostGIS payload collides with checked core: {source.relative_to(extension)}')
PY
cp -a "$extroot/." "$pgroot/"
mv "$pgroot" "$work/assembled/postgresql-relocated"; pgroot="$work/assembled/postgresql-relocated"
python3 "$repo/scripts/macos/static_analysis.py" "$pgroot" arm64 --archive "$core_archive" --archive "$extension" --report "$output/static-analysis.json"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
export PROJ_DATA="$pgroot/share/proj" PROJ_LIB="$pgroot/share/proj" GDAL_DATA="$pgroot/share/gdal"
data_dir="$work/data"; pg_ctl="$pgroot/bin/pg_ctl"
"$pgroot/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >"$work/initdb.log" 2>&1
"$pg_ctl" -D "$data_dir" -l "$work/server.log" -o "-k $work/socket -p 55442 -h ''" -w start
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55442 -d postgres -f "$repo/scripts/postgis/probe.sql" | tee "$output/probe-output.txt"
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55442 -d postgres <<'SQL' | tee "$output/raster-probe.txt"
SET postgis.gdal_enabled_drivers = 'GTiff PNG JPEG';
DO $$ DECLARE r raster; BEGIN
  IF (SELECT count(*) FROM ST_GDALDrivers() WHERE short_name IN ('GTiff','PNG','JPEG')) <> 3 THEN RAISE EXCEPTION 'minimal GDAL drivers are unavailable'; END IF;
  r:=ST_AddBand(ST_MakeEmptyRaster(2,2,0,2,1,-1,0,0,4326),'8BUI'::text,128::double precision,0::double precision);
  IF octet_length(ST_AsTIFF(r))<=0 OR octet_length(ST_AsPNG(r))<=0 OR octet_length(ST_AsJPEG(r))<=0 THEN RAISE EXCEPTION 'raster serialization failed'; END IF;
END $$;
SQL
"$pg_ctl" -D "$data_dir" -m fast -w stop; pg_ctl=; data_dir=
python3 - "$output/static-analysis.json" "$extension" "$core_archive" "$output/publication/postgis-macos-verification.json" <<'PY'
import hashlib,json,pathlib,platform,sys,tarfile,os
report,extension,core,out=map(pathlib.Path,sys.argv[1:])
r=json.loads(report.read_text())
if r.get('passed') is not True or not r.get('inspected_files'): raise SystemExit('fresh-runner Mach-O closure did not pass')
expected={extension.name:hashlib.sha256(extension.read_bytes()).hexdigest(),core.name:hashlib.sha256(core.read_bytes()).hexdigest()}
actual=r.get('archives')
if isinstance(actual,list): actual={item['basename']:item['sha256'] for item in actual}
if actual!=expected: raise SystemExit('static report does not bind final archive bytes')
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'schema_version':1,'outcome':'passed','platform':'macos-arm64','architecture':'arm64','postgresql_version':'18.6','extension':'postgis','version':'3.6.4','build_id':json.loads(tarfile.open(extension,'r:gz').extractfile('metadata.json').read())['build_id'],'source_revision':json.loads(tarfile.open(extension,'r:gz').extractfile('metadata.json').read())['source_revision'],'test_run_id':os.environ.get('GITHUB_RUN_ID'),'test_revision':os.environ.get('GITHUB_SHA'),'runner_os':platform.platform(),'archives':expected,'static_analysis':'static-analysis.json','sql_probes':['probe-output.txt','raster-probe.txt']},indent=2,sort_keys=True)+'\n')
PY
echo 'PASS: PostGIS 3.6.4 archive verified on a fresh macOS arm64 runner'
