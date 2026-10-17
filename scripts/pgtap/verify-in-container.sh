#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
pgtap_archive="pgtap-1.3.4-postgresql-${pg_version}-linux-${architecture}.tar.gz"
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
cd /extension
sha256sum -c "$pgtap_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/extension /tmp/data /tmp/socket
tar -xzf "/input/$pg_archive" -C /tmp/first
tar -xzf "/extension/$pgtap_archive" -C /tmp/extension
pgroot=/tmp/first/postgresql
extroot=/tmp/extension/pgtap
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
test -s "$extroot/LICENSES/pgTAP.txt"
python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path('/tmp/extension')
metadata = json.loads((root / 'metadata.json').read_text())
expected = {
    'project': 'pgtap',
    'version': '1.3.4',
    'sql_names': ['pgtap'],
    'requires': [],
    'configuration_prerequisites': [{
        'type': 'sql_extension', 'name': 'plpgsql',
        'value': 'CREATE EXTENSION plpgsql',
    }],
    'runtime_prerequisites': [],
    'postgresql_version': os.environ['PG_VERSION'],
    'platform': 'linux',
    'architecture': os.environ['PG_ARCHITECTURE'],
    'source': {
        'url': 'https://github.com/theory/pgtap/archive/refs/tags/v1.3.4.tar.gz',
        'sha256': 'd2c951afb296a001d21785611a8e966e3f8fa3f5bfbd929396a5130c0152f314',
    },
}
if metadata != expected:
    raise SystemExit(f'pgTAP package metadata mismatch: {metadata!r}')
inventory = json.loads((root / 'pgtap/LICENSES/pgtap-inventory.json').read_text())
if inventory.get('schema_version') != 1 or len(inventory.get('components', [])) != 1:
    raise SystemExit('pgTAP licence inventory must contain one component')
component = inventory['components'][0]
if component.get('component') != 'pgtap' or component.get('version') != '1.3.4' or component.get('license_file') != 'pgTAP.txt':
    raise SystemExit('pgTAP licence inventory identity mismatch')
if component.get('redistribution_review', {}).get('status') != 'resolved' or component['redistribution_review'].get('source_obligation') != 'none':
    raise SystemExit('pgTAP licence inventory review is incomplete')
extension_dir = root / 'pgtap/share/extension'
if {p.stem for p in extension_dir.glob('*.control')} != {'pgtap'}:
    raise SystemExit('pgTAP package must expose exactly the upstream pgtap extension identity')
for required in ('pgtap--1.3.4.sql', 'pgtap-core--1.3.4.sql', 'pgtap-schema--1.3.4.sql', 'pgtap--1.3.3--1.3.4.sql'):
    if not (extension_dir / required).is_file():
        raise SystemExit(f'pgTAP installed SQL file missing: {required}')
if not (root / 'pgtap/share/doc/extension/pgtap.mmd').is_file():
    raise SystemExit('pgTAP installed documentation missing: pgtap.mmd')
if {p.name for p in root.iterdir()} != {'pgtap', 'metadata.json'}:
    raise SystemExit('pgTAP archive must contain the project payload and sibling metadata.json only')
PY
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then
      continue
    fi
    echo "pgTAP payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv /tmp/first/postgresql /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
cp -a "$extroot/." "$pgroot/"
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" \
  --archive "/input/$pg_archive" --archive "/extension/$pgtap_archive" \
  --report "/analysis/pgtap.json"
useradd -m postgres
chown postgres:postgres /tmp/data /tmp/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -l /tmp/data/server.log -o '-k /tmp/socket -p 55432 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -A -t -v ON_ERROR_STOP=1 -h /tmp/socket -p 55432 -d postgres -f /work/probe.sql | tee /tmp/probe.out
grep -Fxq '1..4' /tmp/probe.out
test "$(grep -Ec '^ok [1-4]( -|$)' /tmp/probe.out)" -eq 4
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
echo "PASS: relocated PostgreSQL ${pg_version} and pgTAP 1.3.4 archives on clean Alpine 3.22"
