#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-build-publication.sh CORE_ARCHIVES TARGET_CONFIG OUTPUT}
target_config=${2:?resolved target config required}
output=${3:?output directory required}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
source "$repo/scripts/macos/core-prefix.sh"
selection=$(python3 - "$target_config" <<'PY'
import json, sys
from pathlib import Path
target=json.loads(Path(sys.argv[1]).read_text())
if (target.get('postgresql_version') != '18.6' or target.get('architecture') != 'arm64'
        or target.get('platform') != 'macos-arm64'):
    raise SystemExit('unsupported selected PostGIS macOS target')
core=target.get('core_archive', {})
if core.get('basename') != 'postgresql-18.6-macos-arm64.tar.gz': raise SystemExit('core identity mismatch')
for key in ('sha256','build_id','source_revision'):
    if not core.get(key): raise SystemExit(f'resolved core lacks {key}')
print(core['basename'],core['sha256'],core['build_id'],core['source_revision'])
PY
)
read -r core_name core_sha core_build_id core_revision <<< "$selection"
core_archives=$(cd "$core_archives" && pwd)
mkdir -p "$output"; output=$(cd "$output" && pwd)
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo 'Build requires native macOS arm64' >&2; exit 1; }
core_archive="$core_archives/$core_name"
test -s "$core_archive" && (cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha" "$core_archive" | shasum -a 256 -c -
work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/postgis-macos-build.XXXXXX")
prefix_link_created=false
cleanup() { macos_remove_core_prefix; rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$work/core" "$work/source" "$work/gdal" "$work/bundle-prefix/lib"
tar -xzf "$core_archive" -C "$work/core"
pgroot="$work/core/postgresql"
find "$pgroot" -type f -print | sort > "$work/core-files.txt"
prefix=$(macos_core_prefix_from_archive "$pgroot" 18.6 arm64 "$core_build_id" "$core_revision")
macos_restore_core_prefix "$prefix" "$pgroot"
prefix_link_created=true
pg_config="$prefix/bin/pg_config"
test "$("$pg_config" --version)" = 'PostgreSQL 18.6'
export MACOSX_DEPLOYMENT_TARGET=11.0
brew_prefix=$(brew --prefix)
for formula in geos proj sfcgal json-c libxml2 protobuf-c pcre2; do brew --prefix "$formula" >/dev/null; done
core_xml="$pgroot/lib/libxml2.16.dylib"
[[ -f "$core_xml" ]] || { echo 'checked core lacks libxml2 2.15.4' >&2; exit 1; }
[[ "$("$(brew --prefix libxml2)/bin/xml2-config" --version)" == 2.15.4 ]] || { echo 'Homebrew libxml2 headers do not match checked core 2.15.4' >&2; exit 1; }
xml2_config="$work/xml2-config"
cat > "$xml2_config" <<EOF
#!/usr/bin/env bash
case "\${1:-}" in
  --cflags) exec "$(brew --prefix libxml2)/bin/xml2-config" --cflags ;;
  --libs) printf '%s\\n' "$core_xml -lz -liconv" ;;
  --version) printf '%s\\n' 2.15.4 ;;
  *) exec "$(brew --prefix libxml2)/bin/xml2-config" "\$@" ;;
esac
EOF
chmod +x "$xml2_config"
for tool in cmake gmake; do command -v "$tool" >/dev/null; done

cd "$work/source"
curl -fL --retry 3 -o gdal.tar.gz https://download.osgeo.org/gdal/3.13.3/gdal-3.13.3.tar.gz
printf '%s  %s\n' 5e0c388d83da2d686cc00a40272882432cdb54edff43d4af173e532844a0a0ea gdal.tar.gz | shasum -a 256 -c -
tar -xzf gdal.tar.gz
gdal_prefix="$work/gdal/prefix"
cmake -S gdal-3.13.3 -B gdal-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$gdal_prefix" \
  -DCMAKE_PREFIX_PATH="$(brew --prefix proj)" -DPROJ_ROOT="$(brew --prefix proj)" \
  -DBUILD_SHARED_LIBS=ON -DBUILD_APPS=OFF -DGDAL_BUILD_OPTIONAL_DRIVERS=OFF \
  -DOGR_BUILD_OPTIONAL_DRIVERS=OFF -DGDAL_ENABLE_DRIVER_PNG=ON -DGDAL_ENABLE_DRIVER_JPEG=ON \
  -DGDAL_USE_EXTERNAL_LIBS=OFF -DGDAL_USE_INTERNAL_LIBS=ON 2>&1 | tee "$output/gdal-configure.log"
cmake --build gdal-build --parallel "$(sysctl -n hw.ncpu)" 2>&1 | tee "$output/gdal-build.log"
cmake --install gdal-build 2>&1 | tee "$output/gdal-install.log"

for path in "$brew_prefix"/lib/*.dylib "$gdal_prefix"/lib/*.dylib; do
  [[ -e "$path" ]] || continue
  name=$(basename "$path")
  if [[ -e "$work/bundle-prefix/lib/$name" ]]; then
    cmp -s "$path" "$work/bundle-prefix/lib/$name" || { echo "dependency prefix collision: $name" >&2; exit 1; }
  else ln -s "$path" "$work/bundle-prefix/lib/$name"; fi
done
export PG_MACOS_DEPENDENCY_PREFIX="$work/bundle-prefix"
export PATH="$gdal_prefix/bin:$PATH"
export PKG_CONFIG_PATH="$gdal_prefix/lib/pkgconfig:$brew_prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export GDAL_DATA="$gdal_prefix/share/gdal"
export LDFLAGS="${LDFLAGS:-} -Wl,-rpath,$gdal_prefix/lib"
cd "$work/source"
curl -fL --retry 3 -o postgis.tar.gz https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz
printf '%s  %s\n' ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6 postgis.tar.gz | shasum -a 256 -c -
tar -xzf postgis.tar.gz
cd postgis-3.6.4
./configure --prefix="$pgroot" --with-pgconfig="$pg_config" --with-gdalconfig="$gdal_prefix/bin/gdal-config" \
  --with-geosconfig="$(brew --prefix geos)/bin/geos-config" --with-projdir="$(brew --prefix proj)" \
  --with-jsondir="$(brew --prefix json-c)" --with-xml2config="$work/xml2-config" \
  --with-sfcgal="$(brew --prefix sfcgal)/bin/sfcgal-config" 2>&1 | tee "$output/configure.log"
gmake -j"$(sysctl -n hw.ncpu)" 2>&1 | tee "$output/build.log"
gmake install 2>&1 | tee "$output/install.log"
python3 - "$pgroot" "$work/core-files.txt" <<'PY'
from pathlib import Path
import re,sys
root=Path(sys.argv[1]); original=set(Path(sys.argv[2]).read_text().splitlines())
names=('postgis','postgis_raster','postgis_sfcgal','postgis_topology')
share=root/'share/extension'; modules=set()
for name in names:
    control=share/f'{name}.control'
    if not control.is_file(): raise SystemExit(f'missing installed {name}.control')
    match=re.search(r"^\s*module_pathname\s*=\s*['\"]?\$libdir/([^'\"\s]+)",control.read_text(),re.M)
    if match: modules.add(match.group(1))
    for sql in share.glob(f'{name}--*.sql'):
        modules.update(re.findall(r'\$libdir/([A-Za-z0-9_.-]+)',sql.read_text()))
if not modules: raise SystemExit('no PostGIS modules were identified from selected SQL files')
for path in (root/'lib').iterdir():
    if str(path) in original or not path.is_file(): continue
    stem=path.name
    if path.suffix in {'.dylib','.so'} and not any(stem in {m,m+'.dylib',m+'.so'} for m in modules): path.unlink()
for path in share.iterdir():
    if str(path) in original: continue
    if not any(path.name in {name, name+'.control'} or path.name.startswith(name+'--') for name in names):
        if path.is_file() or path.is_symlink(): path.unlink()
for path in (root/'bin').iterdir():
    if str(path) not in original and (path.is_file() or path.is_symlink()): path.unlink()
PY
cp -a "$(brew --prefix proj)/share/proj" "$pgroot/share/"
cp -a "$gdal_prefix/share/gdal" "$pgroot/share/"

bundle_root="$work/postgis-bundle-root"
python3 - "$pgroot" "$bundle_root" "$gdal_prefix" <<'PY'
from pathlib import Path
import re, shutil, sys
source, root, gdal_prefix = map(Path, sys.argv[1:])
names = ('postgis','postgis_raster','postgis_sfcgal','postgis_topology')
(root/'lib').mkdir(parents=True,exist_ok=True)
(root/'share/extension').mkdir(parents=True,exist_ok=True)
for path in (source/'lib').glob('*.dylib'):
    shutil.copy2(path,root/'lib'/path.name)
for name in names:
    control=source/'share/extension'/f'{name}.control'
    sql=sorted((source/'share/extension').glob(f'{name}--*.sql'))
    if not control.is_file() or not sql: raise SystemExit(f'missing SQL files for {name}')
    shutil.copy2(control,root/'share/extension'/control.name)
    for path in sql: shutil.copy2(path,root/'share/extension'/path.name)
    modules=set()
    if match:=re.search(r"^\s*module_pathname\s*=\s*['\"]?\$libdir/([^'\"\s]+)",control.read_text(),re.M): modules.add(match.group(1))
    for path in sql: modules.update(re.findall(r'\$libdir/([A-Za-z0-9_.-]+)',path.read_text()))
    for module in modules:
        choices=[source/'lib'/f'{module}{suffix}' for suffix in ('','.dylib','.so')]
        found=[path for path in choices if path.is_file()]
        if len(found)!=1: raise SystemExit(f'expected one installed module for {module}: {found}')
        shutil.copy2(found[0],root/'lib'/found[0].name)
for path in (gdal_prefix/'lib').glob('*.dylib'):
    if path.name.startswith('libgdal'):
        continue
    target=root/'lib'/path.name
    if not target.exists(): target.symlink_to(path.resolve())
gdal_names=[path for path in (gdal_prefix/'lib').glob('libgdal.*.dylib')
            if re.fullmatch(r'libgdal\.\d+\.dylib',path.name)]
if len(gdal_names)!=1: raise SystemExit(f'expected one GDAL soname dylib, found {gdal_names}')
shutil.copy2(gdal_names[0],root/'lib'/gdal_names[0].name)
for relative in ('share/proj','share/gdal'):
    shutil.copytree(source/relative,root/relative,dirs_exist_ok=True)
PY
python3 "$repo/scripts/macos/bundle.py" "$bundle_root" arm64 2>&1 | tee "$output/bundle.log"
python3 - "$bundle_root" "$output" <<'PY'
from pathlib import Path
import json, shutil, subprocess, sys
root, output = map(Path, sys.argv[1:])
package = output / 'package/postgis'
package.mkdir(parents=True, exist_ok=True)
dependencies = json.loads((root / 'bundled-dependencies.json').read_text())
(output / 'postgis-bundled-dependencies.json').write_text(json.dumps(dependencies, indent=2, sort_keys=True) + '\n')
PY
python3 - "$bundle_root" "$output" <<'PY'
import json, pathlib, shutil, sys
root, output=map(pathlib.Path,sys.argv[1:])
package=output/'package/postgis'
for directory in ('lib','share/extension','share/proj','share/gdal'):
    (package/directory).mkdir(parents=True,exist_ok=True)
names=('postgis','postgis_raster','postgis_sfcgal','postgis_topology')
for name in names:
    control=root/'share/extension'/f'{name}.control'
    sql=sorted((root/'share/extension').glob(f'{name}--*.sql'))
    if not control.is_file() or not sql: raise SystemExit(f'missing SQL files for {name}')
    shutil.copy2(control,package/'share/extension'/control.name)
    for path in sql: shutil.copy2(path,package/'share/extension'/path.name)
    modules=set()
    import re
    if match:=re.search(r"^\s*module_pathname\s*=\s*['\"]?\$libdir/([^'\"\s]+)",control.read_text(),re.M): modules.add(match.group(1))
    for path in sql: modules.update(re.findall(r'\$libdir/([A-Za-z0-9_.-]+)',path.read_text()))
    for module in modules:
        choices=[root/'lib'/f'{module}{suffix}' for suffix in ('','.dylib','.so')]
        found=[path for path in choices if path.is_file()]
        if len(found)!=1: raise SystemExit(f'expected one installed module for {module}: {found}')
        shutil.copy2(found[0],package/'lib'/found[0].name)
for relative in ('share/proj','share/gdal'):
    shutil.copytree(root/relative,package/relative,dirs_exist_ok=True)
dependency_map=json.loads((output/'postgis-bundled-dependencies.json').read_text())
for name in dependency_map:
    path=root/'lib'/name
    if path.is_file(): shutil.copy2(path,package/'lib'/name)
for path in (root/'lib').glob('libgdal*.dylib'):
    if path.is_file(): shutil.copy2(path,package/'lib'/path.name)
(package/'LICENSES').mkdir(exist_ok=True)
(package/'bundled-dependencies.json').write_text(json.dumps(dependency_map,indent=2,sort_keys=True)+'\n')
PY
cp "$work/source/postgis-3.6.4/COPYING" "$output/package/postgis/LICENSES/PostGIS.txt"
cp "$work/source/gdal-3.13.3/LICENSE.TXT" "$output/package/postgis/LICENSES/GDAL.txt"
python3 "$repo/scripts/postgis/macos-license-inventory.py" "$output/package/postgis" "$pgroot" "$brew_prefix" "$work/source/postgis.tar.gz" "$work/source/gdal.tar.gz"
mv "$output/package/postgis/bundled-dependencies.json" "$output/package/postgis/LICENSES/postgis-bundled-dependencies.json"
python3 - "$output/package/metadata.json" "$core_name" "$core_sha" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); core,sha=sys.argv[2:]
p.write_text(json.dumps({'project':'postgis','version':'3.6.4','sql_names':['postgis','postgis_raster','postgis_sfcgal','postgis_topology'],'requires':[],'configuration_prerequisites':[],'runtime_prerequisites':[{'type':'environment_variable','name':'PROJ_DATA','value_relative_to_prefix':'share/proj'},{'type':'environment_variable','name':'PROJ_LIB','value_relative_to_prefix':'share/proj'},{'type':'environment_variable','name':'GDAL_DATA','value_relative_to_prefix':'share/gdal'}],'postgresql_version':'18.6','platform':'macos','architecture':'arm64','build_id':f"github-{__import__('os').environ['GITHUB_RUN_ID']}-{__import__('os').environ['GITHUB_RUN_ATTEMPT']}",'source_revision':__import__('os').environ['GITHUB_SHA'],'build_configuration':'native-macos;deployment-target=11.0;gdal=3.13.3;gdal-drivers=GTiff,PNG,JPEG','source':{'url':'https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz','sha256':'ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6'},'core_archive':{'basename':core,'sha256':sha}},indent=2,sort_keys=True)+'\n')
PY
archive=postgis-3.6.4-postgresql-18.6-macos-arm64.tar.gz
tar -C "$output/package" -czf "$output/$archive" postgis metadata.json
(cd "$output" && shasum -a 256 "$archive" > "$archive.sha256")
echo "PASS: built PostGIS 3.6.4 macOS arm64 archive"
