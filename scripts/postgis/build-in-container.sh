#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
if [[ ! "$pg_version" =~ ^[0-9]+\.[0-9]+$ ]]; then
  echo "Unsupported PostgreSQL version format: $pg_version" >&2
  exit 2
fi
postgis_version=3.6.4
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
postgis_archive="postgis-${postgis_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
mkdir -p /work/prefix /work/source /work/stage/postgis/{lib,share/extension,LICENSES/postgis} /out
tar -xzf "$pg_archive" -C /work/prefix
mv /work/prefix/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
export PATH="$pgroot/bin:$PATH"
cd /work/source
curl -fL --retry 3 -o postgis.tar.gz "https://download.osgeo.org/postgis/source/postgis-${postgis_version}.tar.gz"
printf '%s  %s\n' 'ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6' postgis.tar.gz | sha256sum -c -
postgis_source_sha256=$(sha256sum postgis.tar.gz | cut -d' ' -f1)
tar -xzf postgis.tar.gz
cd "postgis-${postgis_version}"
./configure --with-pgconfig="$pgroot/bin/pg_config" --with-sfcgal=/usr/bin/sfcgal-config
make -j 4
make install

# Stage only the SQL extensions declared for PostGIS in support.json.
stage=/work/stage/postgis
python3 - <<'PY'
import json
import os
import pathlib
import re
import shutil

pgroot = pathlib.Path('/opt/postgresql')
stage = pathlib.Path('/work/stage/postgis')
support = json.loads(pathlib.Path('/work/support.json').read_text())
allowed = support['extensions']['PostGIS']['sql_names']
source_share = pgroot / 'share/extension'
source_lib = pgroot / 'lib'

for name in allowed:
    control = source_share / f'{name}.control'
    if not control.is_file():
        raise SystemExit(f'Missing supported extension control file: {control}')
    shutil.copy2(control, stage / 'share/extension' / control.name)
    sql_files = list(source_share.glob(f'{name}--*.sql'))
    if not sql_files:
        raise SystemExit(f'Missing SQL version files for supported extension {name}')
    modules = set()
    for sql in sql_files:
        shutil.copy2(sql, stage / 'share/extension' / sql.name)
        modules.update(re.findall(r'\$libdir/([A-Za-z0-9_.-]+)', sql.read_text()))

    text = control.read_text()
    module = re.search(r"^\s*module_pathname\s*=\s*['\"]?\$libdir/([^'\"\s]+)", text, re.M)
    if module:
        modules.add(module.group(1))
    if not modules:
        raise SystemExit(f'No $libdir module reference in SQL files or control for {name}')
    for module_name in modules:
        library = source_lib / f'{module_name}.so'
        if not library.is_file():
            raise SystemExit(f'Missing module library {library} for {name}')
        shutil.copy2(library, stage / 'lib' / library.name)
PY
cp COPYING "$stage/LICENSES/postgis/PostGIS.txt"
cp -a /usr/share/common-licenses "$stage/LICENSES/postgis/common-licenses"
mkdir -p "$stage/lib/runtime" "$stage/share"
: > /work/runtime-map.tsv
cp -a /usr/share/proj "$stage/share/proj"
cp -a /usr/share/gdal "$stage/share/gdal"
cp /usr/share/doc/proj-data/copyright "$stage/LICENSES/postgis/proj-data.copyright"
cp /usr/share/doc/gdal-data/copyright "$stage/LICENSES/postgis/gdal-data.copyright"
# Bundle the ELF dependency closure for the selected SQL modules. The
# PostgreSQL archive supplies glibc and libpq; SFCGAL and GDAL add C++ libraries.
for pass in 1 2 3 4; do
  while IFS= read -r -d '' elf; do
    if ! file -b "$elf" | grep -q ELF; then continue; fi
    while read -r library path; do
      [[ -f "$path" ]] || continue
      case "$library" in
        linux-vdso*|ld-linux*|libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|libresolv.so*|libnss_*|libpq.so*) continue ;;
      esac
      case "$path" in "$pgroot"/lib/*|"$stage"/lib/*) continue ;; esac
      dest="$stage/lib/runtime/$library"
      if [[ ! -e "$dest" ]]; then
        cp -L "$path" "$dest"
        resolved=$(readlink -f "$path")
        package=$(dpkg-query -S "$path" "$resolved" 2>/dev/null | head -1 | cut -d: -f1 || true)
        if [[ -z "$package" ]]; then
          package=$(dpkg-query -S "*/$(basename "$resolved")" 2>/dev/null | head -1 | cut -d: -f1 || true)
        fi
        if [[ -z "$package" || ! -f "/usr/share/doc/$package/copyright" ]]; then
          echo "No package copyright found for $library ($path)" >&2
          exit 1
        fi
        cp "/usr/share/doc/$package/copyright" "$stage/LICENSES/postgis/${package}.copyright"
        printf '%s\t%s\n' "$package" "lib/runtime/$library" >> /work/runtime-map.tsv
      fi
    done < <(ldd "$elf" 2>/dev/null | awk '$2 == "=>" && $3 ~ /^\// {print $1, $3}')
  done < <(find "$stage/lib" -type f -print0)
done
while IFS= read -r -d '' elf; do
  if ! file -b "$elf" | grep -q ELF; then continue; fi
  case "$elf" in
    "$stage/lib/runtime/"*) rpath='$ORIGIN' ;;
    *) rpath='$ORIGIN:$ORIGIN/runtime' ;;
  esac
  patchelf --set-rpath "$rpath" "$elf"
done < <(find "$stage/lib" -type f -print0)
python3 - <<'PY'
from pathlib import Path
import filecmp

stage = Path('/work/stage/postgis')
core_runtime = Path('/opt/postgresql/lib/runtime')
for library in (stage / 'lib/runtime').iterdir():
    supplied = core_runtime / library.name
    if not supplied.exists():
        continue
    if not filecmp.cmp(library, supplied, shallow=False):
        raise SystemExit(f'PostGIS runtime library differs from PostgreSQL archive: {library.name}')
    library.unlink()

runtime_map = Path('/work/runtime-map.tsv')
runtime_map.write_text(''.join(
    line for line in runtime_map.read_text().splitlines(keepends=True)
    if (stage / line.rstrip('\n').split('\t', 1)[1]).exists()
))
PY
python3 /usr/local/bin/write-postgis-license-inventory \
  "$stage" /work/runtime-map.tsv "$postgis_source_sha256"
python3 - "$architecture" "$postgis_source_sha256" <<'PY'
import json
import os
from pathlib import Path
import sys

sql_names = json.loads(Path('/work/support.json').read_text())['extensions']['PostGIS']['sql_names']
metadata = {
    'project': 'postgis',
    'version': '3.6.4',
    'sql_names': sql_names,
    'requires': [],
    'configuration_prerequisites': [],
    'runtime_prerequisites': [
        {'type': 'environment_variable', 'name': name, 'value_relative_to_prefix': value}
        for name, value in (
            ('PROJ_LIB', 'share/proj'),
            ('PROJ_DATA', 'share/proj'),
            ('GDAL_DATA', 'share/gdal'),
        )
    ],
    'postgresql_version': os.environ.get('PG_VERSION', '18.6'),
    'platform': 'linux',
    'architecture': sys.argv[1],
    'source': {
        'url': 'https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz',
        'sha256': sys.argv[2],
    },
}
Path('/work/stage/metadata.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
PY

# Test installed extensions against the extracted PostgreSQL archive. Runtime
# library and data closure is recorded separately; this phase tests function.
useradd -m postgres
mkdir -p /work/data /work/socket
chown postgres:postgres /work/data /work/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /work/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -o '-k /work/socket -p 55432 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /work/socket -p 55432 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m fast -w stop
trap - EXIT
cd /work/stage
tar -czf "/out/$postgis_archive" postgis metadata.json
cd /out
sha256sum "$postgis_archive" > "$postgis_archive.sha256"
python3 /usr/local/bin/create-linux-symbols "$postgis_archive" --output-dir /out/debug-symbols
du -sh /work/stage/postgis "$stage/lib/runtime" "$stage/share/proj" "$stage/share/gdal"
