#!/usr/bin/env bash
set -euo pipefail

architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
if [[ ! "$pg_version" =~ ^(16|17|18)\.[0-9]+$ ]]; then
  echo "TIGER Geocoder supports PostgreSQL 16-18 selected minors: $pg_version" >&2
  exit 2
fi
core_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
postgis_archive="postgis-3.6.4-postgresql-${pg_version}-linux-${architecture}.tar.gz"
tiger_archive="postgis_tiger_geocoder-2025.2-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /core && sha256sum -c "${core_archive}.sha256"
cd /postgis && sha256sum -c "${postgis_archive}.sha256"
cd /tiger && sha256sum -c "${tiger_archive}.sha256"

mkdir -p /tmp/install /tmp/postgis /tmp/tiger /tmp/data /tmp/socket
tar -xzf "/core/$core_archive" -C /tmp/install
tar -xzf "/postgis/$postgis_archive" -C /tmp/postgis
tar -xzf "/tiger/$tiger_archive" -C /tmp/tiger
python3 - "$architecture" "$pg_version" <<'PY'
import json
from pathlib import Path
import shutil
import sys

architecture = sys.argv[1]
pg_version = sys.argv[2]
root = Path('/tmp/tiger')
assert {entry.name for entry in root.iterdir()} == {'postgis_tiger_geocoder', 'metadata.json'}
metadata = json.loads((root / 'metadata.json').read_text())
assert metadata['project'] == 'postgis_tiger_geocoder'
assert metadata['version'] == '2025.2'
assert metadata['sql_names'] == ['postgis_tiger_geocoder']
assert metadata['requires'] == ['PostGIS']
assert {'type': 'sql_extension', 'name': 'fuzzystrmatch',
        'value': 'CREATE EXTENSION fuzzystrmatch'} in metadata['configuration_prerequisites']
assert metadata['postgresql_version'] == pg_version
assert metadata['platform'] == 'linux' and metadata['architecture'] == architecture
payload = root / 'postgis_tiger_geocoder'
assert (payload / 'share/extension/postgis_tiger_geocoder.control').is_file()
assert (payload / 'share/extension/postgis_tiger_geocoder--2025.2.sql').is_file()
assert (payload / 'LICENSES/postgis_tiger_geocoder/COPYING').is_file()
inventory = json.loads((payload / 'LICENSES/postgis_tiger_geocoder-inventory.json').read_text())
assert inventory['components'][0]['source_sha256'] == metadata['source']['sha256']

prefix = Path('/tmp/install/postgresql')
for project, source in (
    ('postgis', Path('/tmp/postgis/postgis')),
    ('postgis_tiger_geocoder', Path('/tmp/tiger/postgis_tiger_geocoder')),
):
    for path in source.rglob('*'):
        relative = path.relative_to(source)
        target = prefix / relative
        if path.is_symlink():
            if target.exists() or target.is_symlink():
                raise SystemExit(f'{project} payload collision: {relative}')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(path.readlink())
        elif path.is_dir():
            if target.exists() and not target.is_dir():
                raise SystemExit(f'{project} payload collision: {relative}')
            target.mkdir(parents=True, exist_ok=True)
        else:
            if target.exists() or target.is_symlink():
                raise SystemExit(f'{project} payload collision: {relative}')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
PY
pgroot=/tmp/install/postgresql
test -s "$pgroot/share/extension/postgis_tiger_geocoder.control"
test -s "$pgroot/share/extension/postgis_tiger_geocoder--2025.2.sql"
test "$("$pgroot/bin/pg_config" --sharedir)" = "$pgroot/share"
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" \
  --archive "/core/$core_archive" --archive "/postgis/$postgis_archive" \
  --archive "/tiger/$tiger_archive" --report /analysis/tiger.json
export PROJ_LIB="$pgroot/share/proj" PROJ_DATA="$pgroot/share/proj" GDAL_DATA="$pgroot/share/gdal"
useradd -m postgres
chown postgres:postgres /tmp/data /tmp/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -l /tmp/data/server.log -o '-k /tmp/socket -p 55434 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55434 -d postgres -f /repo/scripts/tiger/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
echo 'PASS: relocated PostgreSQL, PostGIS and TIGER Geocoder archives on clean verifier'
