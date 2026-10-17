#!/usr/bin/env bash
set -euo pipefail

architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
version=2025.2
pg_version=18.6
source_name="postgis_tiger_geocoder-${version}.tar.gz"
source_sha256=c33cfbfb40785db8754a36be66060e8d023773e7e1be8fb8a622bb3c48db9f54
core_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
tiger_archive="postgis_tiger_geocoder-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"

cd /core
sha256sum -c "${core_archive}.sha256"
mkdir -p /work/prefix /work/source /work/stage/postgis_tiger_geocoder/share/extension /work/stage/postgis_tiger_geocoder/LICENSES/postgis_tiger_geocoder /out
tar -xzf "$core_archive" -C /work/prefix
mv /work/prefix/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = 'PostgreSQL 18.6'

if [[ -f "/source/$source_name" ]]; then
  cp "/source/$source_name" /work/source/
else
  curl -fL --retry 3 -o "/work/source/$source_name" \
    "https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/$source_name"
fi
printf '%s  %s\n' "$source_sha256" "/work/source/$source_name" | sha256sum -c -
tar -xzf "/work/source/$source_name" -C /work/source
cd /work/source/postgis_tiger_geocoder
make PG_CONFIG="$pgroot/bin/pg_config" all

stage=/work/stage/postgis_tiger_geocoder
cp postgis_tiger_geocoder.control "$stage/share/extension/"
find data -maxdepth 1 -type f -name 'postgis_tiger_geocoder*.sql' -exec cp {} "$stage/share/extension/" \;
test -s "$stage/share/extension/postgis_tiger_geocoder--${version}.sql"
cp COPYING "$stage/LICENSES/postgis_tiger_geocoder/COPYING"
python3 - "$stage" "$version" "$pg_version" "$architecture" "$source_sha256" <<'PY'
import json
from pathlib import Path
import sys

stage, version, pg_version, architecture, source_sha256 = sys.argv[1:]
stage = Path(stage)
sql_files = sorted(path.name for path in (stage / 'share/extension').glob('*.sql'))
if not sql_files:
    raise SystemExit('TIGER Geocoder build produced no SQL scripts')
inventory = {
    'schema_version': 1,
    'components': [{
        'component': 'PostGIS TIGER Geocoder',
        'version': version,
        'payload_paths': ['share/extension'],
        'license_file': 'COPYING',
        'source_url': f'https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-{version}.tar.gz',
        'source_sha256': source_sha256,
    }],
}
(stage / 'LICENSES/postgis_tiger_geocoder/inventory.json').write_text(json.dumps(inventory, indent=2, sort_keys=True) + '\n')
metadata = {
    'project': 'postgis_tiger_geocoder',
    'version': version,
    'sql_names': ['postgis_tiger_geocoder'],
    'requires': ['PostGIS'],
    'configuration_prerequisites': [{
        'type': 'postgresql_setting', 'name': 'search_path',
        'value': '"$user",public,tiger',
    }],
    'runtime_prerequisites': [],
    'postgresql_version': pg_version,
    'platform': 'linux',
    'architecture': architecture,
    'source': {'url': inventory['components'][0]['source_url'], 'sha256': source_sha256},
}
Path('/work/stage/metadata.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
PY
cd /work/stage
tar -czf "/out/$tiger_archive" postgis_tiger_geocoder metadata.json
cd /out
sha256sum "$tiger_archive" > "$tiger_archive.sha256"
