#!/usr/bin/env bash
set -euo pipefail

core_archive=${1:?usage: windows-build.sh CORE_ARCHIVE OUTPUT_ROOT CORE_IDENTITY}
output_root=${2:?usage: windows-build.sh CORE_ARCHIVE OUTPUT_ROOT}
core_identity=${3:?usage: windows-build.sh CORE_ARCHIVE OUTPUT_ROOT CORE_IDENTITY}
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
recipe_root="$repo_root/scripts/postgis"
pg_version=$(python - "$core_identity" "$core_archive" <<'PY'
import json, re, sys
from pathlib import Path
value=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
archive=Path(sys.argv[2])
match=re.fullmatch(r'postgresql-(15\.19|16\.15|17\.11|18\.6)-windows-x86_64\.tar\.gz',archive.name)
if not match or value.get('status') != 'checked' or Path(value.get('archive','')).name != archive.name:
    raise SystemExit('core archive does not match a checked selected PostgreSQL identity')
print(match.group(1))
PY
)
export PG_VERSION="$pg_version"
mkdir -p "$output_root"
output_root=$(cd "$output_root" && pwd)
bash "$recipe_root/windows-mingw-build.sh" "$output_root/mingw" "$pg_version"

set -x
test "${MSYSTEM:-}" = MINGW64
mkdir -p "$output_root/selected" "$output_root/package/postgis"
tar -xzf "$core_archive" -C "$output_root/selected"
selected="$output_root/selected/postgresql"
mingw="$output_root/mingw/postgresql"
netcdf="$output_root/mingw/netcdf-no-ros3"
test "$("$selected/bin/pg_config.exe" --version)" = "PostgreSQL $pg_version"
test "$("$mingw/bin/pg_config.exe" --version)" = "PostgreSQL $pg_version"

shopt -s nullglob
modules=("$mingw"/lib/postgis*.dll "$mingw"/lib/rtpostgis*.dll)
sql=("$mingw"/share/extension/postgis*.sql "$mingw"/share/extension/postgis*.control)
test "${#modules[@]}" -gt 0
test "${#sql[@]}" -gt 0
package="$output_root/package/postgis"
mkdir -p "$package/bin" "$package/lib" "$package/share/extension" "$package/share/gdal" "$package/share/proj"
cp "${modules[@]}" "$package/lib/"
cp "${sql[@]}" "$package/share/extension/"
for data_dir in gdal proj sfcgal; do
  if test -d "/mingw64/share/$data_dir"; then
    mkdir -p "$package/share/$data_dir"
    cp -a "/mingw64/share/$data_dir/." "$package/share/$data_dir/"
  fi
done

module_names="$output_root/module-names.txt"
printf '%s\n' "${modules[@]##*/}" | sort -fu > "$module_names"
for module in "${modules[@]}"; do
  report="$output_root/$(basename "$module").json"
  resolved="$output_root/$(basename "$module").modules.json"
  python "$recipe_root/windows-diagnose-imports.py" --root "$module" \
    --search-directory "$selected/bin" --search-directory "$selected/lib" \
    --search-directory "$netcdf/bin" --search-directory "$mingw/bin" \
    --search-directory "$mingw/lib" --search-directory /mingw64/bin \
    --search-directory /mingw64/lib --search-directory /usr/bin \
    --output "$report" --modules-output "$resolved"
  python - "$report" <<'PY'
import json, sys
from pathlib import Path
report=json.loads(Path(sys.argv[1]).read_text())
findings=report['missing_symbols']+report['unresolved_dlls']+report['objdump_errors']
if findings:
    raise SystemExit(json.dumps(findings, indent=2))
PY
  python - "$resolved" "$package/bin" "$module_names" "$selected/bin" <<'PY'
import filecmp, json, shutil, sys
from pathlib import Path
resolved, destination, roots, selected_bin=map(Path, sys.argv[1:])
root_names={line.casefold() for line in roots.read_text().splitlines()}
core_dlls={path.name.casefold() for path in selected_bin.glob('*.dll')}
for value in json.loads(resolved.read_text()):
    source=Path(value)
    if source.suffix.casefold()=='.dll' and source.name.casefold() not in root_names|core_dlls:
        target=destination/source.name
        if target.exists() and not filecmp.cmp(source,target,shallow=False):
            raise SystemExit(f'conflicting runtime DLLs: {target}')
        if not target.exists(): shutil.copy2(source,target)
PY
done

python - "$output_root" "$package/bin" "$output_root/runtime-package-owners.txt" <<'PY'
import json, subprocess, sys
from pathlib import Path
root, bundled, output=map(Path,sys.argv[1:])
sources={}
for report in root.glob('*.modules.json'):
    for value in json.loads(report.read_text()):
        source=Path(value)
        if (bundled/source.name).is_file(): sources.setdefault(source.name.casefold(),source)
with output.open('w') as stream:
    for name,source in sorted(sources.items()):
        owner=subprocess.run(['pacman','-Qo',str(source)],capture_output=True,text=True)
        stream.write(f"{name}\t{source}\t{owner.stdout.strip() if owner.returncode==0 else 'source-built or unowned'}\n")
PY

for file in "${sql[@]}"; do cp "$file" "$selected/share/extension/"; done
for file in "${modules[@]}"; do cp "$file" "$selected/lib/"; done
archive="$output_root/postgis-3.6.4-postgresql-$pg_version-windows-x86_64.tar.gz"
python - "$package/metadata.json" "$core_archive" "$core_identity" <<'PY'
import hashlib, json, os, re, sys
from pathlib import Path
metadata, core, identity_path=map(Path, sys.argv[1:])
digest=hashlib.sha256(core.read_bytes()).hexdigest()
identity=json.loads(identity_path.read_text())
if identity.get('status') != 'checked' or identity.get('sha256') != digest:
    raise SystemExit('PostgreSQL archive does not match a checked selected core')
run_id=os.environ.get('GITHUB_RUN_ID', '')
attempt=os.environ.get('GITHUB_RUN_ATTEMPT', '')
revision=os.environ.get('GITHUB_SHA', '')
if not run_id.isdigit() or not attempt.isdigit() or not re.fullmatch(r'[0-9a-f]{40}', revision):
    raise SystemExit('GitHub Actions build provenance is required')
metadata.write_text(json.dumps({
  'schema_version': 1, 'project': 'PostGIS', 'version': '3.6.4',
  'sql_names': ['postgis','postgis_raster','postgis_sfcgal','postgis_topology'],
  'requires': [],
  'postgresql_version': os.environ['PG_VERSION'], 'platform': 'windows', 'architecture': 'x86_64',
  'source': {'url':'https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz',
             'sha256':'ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6'},
  'core_archive': {'basename':core.name,'sha256':digest},
  'build_id': f'github-{run_id}-{attempt}', 'source_revision': revision,
  'release_eligible':False, 'core_status':identity['status']
}, indent=2, sort_keys=True)+'\n')
PY
python "$repo_root/tools/license_pointer.py" write "$package" postgis
tar -czf "$archive" -C "$output_root/package" postgis
python "$repo_root/tools/license_pointer.py" verify "$archive" postgis
(cd "$output_root" && sha256sum "${archive##*/}" > "${archive##*/}.sha256")
