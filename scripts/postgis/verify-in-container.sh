#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
if [[ ! "$pg_version" =~ ^[0-9]+\.[0-9]+$ ]]; then
  echo "Unsupported PostgreSQL version format: $pg_version" >&2
  exit 2
fi
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
build_version=${POSTGIS_BUILD_PG_VERSION:-$pg_version}
if [[ ! $build_version =~ ^[0-9]+\.[0-9]+$ ]]; then
  echo "Unsupported PostGIS build PostgreSQL version format: $build_version" >&2
  exit 2
fi
postgis_archive=${POSTGIS_ARCHIVE_NAME:-postgis-3.6.4-postgresql-${pg_version}-linux-${architecture}.tar.gz}
if [[ $postgis_archive != "$(basename -- "$postgis_archive")" || $postgis_archive == . || $postgis_archive == .. || ! $postgis_archive =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "POSTGIS_ARCHIVE_NAME must be a basename without path separators: $postgis_archive" >&2
  exit 2
fi
cd /input
sha256sum -c "$pg_archive.sha256"
cd /out
sha256sum -c "$postgis_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/extension /tmp/data /tmp/socket
tar -xzf "/input/$pg_archive" -C /tmp/first
tar -xzf "/out/$postgis_archive" -C /tmp/extension
python3 - <<'PY'
import json
import os
import pathlib
import re

support = json.loads(pathlib.Path('/work/support.json').read_text())
allowed = set(support['extensions']['PostGIS']['sql_names'])
archive_root = pathlib.Path('/tmp/extension')
assert {path.name for path in archive_root.iterdir()} == {'postgis', 'metadata.json'}
with (archive_root / 'metadata.json').open() as stream:
    metadata = json.load(stream)
assert metadata == {
    'project': 'postgis',
    'version': '3.6.4',
    'sql_names': support['extensions']['PostGIS']['sql_names'],
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
    'postgresql_version': os.environ.get('POSTGIS_BUILD_PG_VERSION', os.environ.get('PG_VERSION', '18.6')),
    'platform': 'linux',
    'architecture': os.environ.get('PG_ARCHITECTURE', 'x86_64'),
    'source': {
        'url': 'https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz',
        'sha256': 'ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6',
    },
}, metadata
assert not (archive_root / 'postgis/manifest.json').exists()
extension_dir = pathlib.Path('/tmp/extension/postgis/share/extension')
controls = {path.stem for path in extension_dir.glob('*.control')}
assert controls == allowed, f'PostGIS control files {sorted(controls)} != support.json {sorted(allowed)}'

expected_modules = set()
for name in allowed:
    control = extension_dir / f'{name}.control'
    text = control.read_text()
    match = re.search(r"^\s*module_pathname\s*=\s*['\"]?\$libdir/([^'\"\s]+)", text, re.M)
    scripts = list(extension_dir.glob(f'{name}--*.sql'))
    assert scripts, f'No SQL version files for supported extension {name}'
    modules = set()
    for script in scripts:
        modules.update(re.findall(r'\$libdir/([A-Za-z0-9_.-]+)', script.read_text()))
    if match:
        modules.add(match.group(1))
    assert modules, f'No $libdir module references for supported extension {name}'
    expected_modules.update(module + '.so' for module in modules)
lib_dir = pathlib.Path('/tmp/extension/postgis/lib')
module_libraries = {path.name for path in lib_dir.glob('*.so*')}
assert module_libraries == expected_modules, (
    f'PostGIS module libraries {sorted(module_libraries)} != expected {sorted(expected_modules)}')
assert not (pathlib.Path('/tmp/extension/postgis') / 'bin').exists()

for path in extension_dir.glob('*.sql'):
    name = path.name.split('--', 1)[0]
    assert name in allowed, f'Unselected SQL script in archive: {path.name}'
PY
python3 /usr/local/bin/check-postgis-license-inventory /tmp/extension/postgis
mv /tmp/first/postgresql /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
extroot=/tmp/extension/postgis
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then
      continue
    fi
    echo "PostGIS payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
cp -a "$extroot/." "$pgroot/"
test -s "$extroot/LICENSES/postgis/proj-data.copyright"
test -s "$extroot/LICENSES/postgis/gdal-data.copyright"
python3 /usr/local/bin/check-elf-dependencies "$pgroot"
export PROJ_LIB="$pgroot/share/proj" PROJ_DATA="$pgroot/share/proj" GDAL_DATA="$pgroot/share/gdal"
useradd -m postgres
chown postgres:postgres /tmp/data /tmp/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -l /tmp/data/server.log -o '-k /tmp/socket -p 55433 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55433 -d postgres -f /work/probe.sql
if grep -Eq 'proj_create|proj\.db|ERROR:.*PROJ' /tmp/data/server.log; then
  cat /tmp/data/server.log >&2
  echo 'PROJ runtime data error in server log' >&2
  exit 1
fi
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
echo 'PASS: relocated PostgreSQL and PostGIS archives on clean verifier'
