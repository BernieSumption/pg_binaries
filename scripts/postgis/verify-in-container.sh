#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_archive="postgresql-18.6-linux-${architecture}.tar.gz"
postgis_archive="postgis-3.6.4-postgresql-18.6-linux-${architecture}.tar.gz"
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

with open('/tmp/extension/postgis/manifest.json') as f:
    m = json.load(f)
assert (m['schema_version'], m['component'], m['version'], m['postgresql_version'],
        m['platform'], m['architecture']) == (1, 'postgis', '3.6.4', '18.6', 'linux', os.environ.get('PG_ARCHITECTURE', 'x86_64')), m

support = json.loads(pathlib.Path('/work/support.json').read_text())
allowed = set(support['extensions']['PostGIS']['sql_names'])
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
while IFS= read -r -d '' library; do
  existing="$pgroot/lib/${library#"$extroot/lib/"}"
  if [[ -e "$existing" ]] && ! cmp -s "$library" "$existing"; then
    echo "Library collision with different bytes: ${library#"$extroot/lib/"}" >&2
    exit 1
  fi
done < <(find "$extroot/lib" -type f -print0)
cp -an "$extroot/lib/." "$pgroot/lib/"
cp -a "$extroot/share/extension/." "$pgroot/share/extension/"
cp -a "$extroot/share/proj" "$extroot/share/gdal" "$pgroot/share/"
test -s "$extroot/LICENSES/proj-data.copyright"
test -s "$extroot/LICENSES/gdal-data.copyright"
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
