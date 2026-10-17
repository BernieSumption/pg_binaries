#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
hypopg_archive="hypopg-1.4.3-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
cd /extension
sha256sum -c "$hypopg_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/extension /tmp/data /tmp/socket
tar -xzf "/input/$pg_archive" -C /tmp/first
tar -xzf "/extension/$hypopg_archive" -C /tmp/extension
pgroot=/tmp/first/postgresql
extroot=/tmp/extension/hypopg
test "$(/tmp/first/postgresql/bin/pg_config --version)" = "PostgreSQL $pg_version"
test -s "$extroot/LICENSES/HypoPG.txt"
python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path('/tmp/extension')
metadata = json.loads((root / 'metadata.json').read_text())
expected = {
    'project': 'hypopg',
    'version': '1.4.3',
    'sql_names': ['hypopg'],
    'requires': [],
    'configuration_prerequisites': [],
    'runtime_prerequisites': [],
    'postgresql_version': os.environ['PG_VERSION'],
    'platform': 'linux',
    'architecture': os.environ['PG_ARCHITECTURE'],
    'source': {
        'url': 'https://github.com/HypoPG/hypopg/archive/refs/tags/1.4.3.tar.gz',
        'sha256': '498a961d88cf37057fd9e98027d06fe805c8959d51895c3d9b94c9eb4e14f706',
    },
}
if metadata != expected:
    raise SystemExit(f'HypoPG package metadata mismatch: {metadata!r}')
inventory = json.loads((root / 'hypopg/LICENSES/inventory.json').read_text())
if inventory.get('schema_version') != 1 or len(inventory.get('components', [])) != 1:
    raise SystemExit('HypoPG licence inventory must contain one component')
component = inventory['components'][0]
for key, value in {
    'component': 'hypopg',
    'version': '1.4.3',
    'payload_paths': ['lib/hypopg.so', 'share/extension'],
    'license_file': 'HypoPG.txt',
    'source_url': expected['source']['url'],
    'source_sha256': expected['source']['sha256'],
}.items():
    if component.get(key) != value:
        raise SystemExit(f'HypoPG licence inventory {key} mismatch')
review = component.get('redistribution_review', {})
if (review.get('status') != 'resolved' or not review.get('basis')
        or review.get('source_obligation') != 'none'):
    raise SystemExit('HypoPG redistribution review is incomplete')
license_text = (root / 'hypopg/LICENSES/HypoPG.txt').read_text()
for fragment in (
    'Permission to use, copy, modify, and distribute this software',
    'provided that the above copyright notice and this paragraph and',
    'THE UNIVERSITY OF CALIFORNIA SPECIFICALLY DISCLAIMS ANY WARRANTIES',
):
    if fragment not in license_text:
        raise SystemExit(f'HypoPG upstream licence text is incomplete: {fragment}')
if {p.stem for p in (root / 'hypopg/share/extension').glob('*.control')} != {'hypopg'}:
    raise SystemExit('HypoPG payload must contain exactly the hypopg SQL extension')
if not (root / 'hypopg/lib/hypopg.so').is_file():
    raise SystemExit('HypoPG shared library missing from payload')
if {p.name for p in root.iterdir()} != {'hypopg', 'metadata.json'}:
    raise SystemExit('HypoPG archive must contain payload and sibling metadata.json only')
PY

if [[ -e "$pgroot/LICENSES/hypopg" || -L "$pgroot/LICENSES/hypopg" ]]; then
  echo 'HypoPG licence destination already exists in PostgreSQL archive' >&2
  exit 1
fi
mkdir -p "$pgroot/LICENSES/hypopg"
mv "$extroot/LICENSES/"* "$pgroot/LICENSES/hypopg/"
rmdir "$extroot/LICENSES"

while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then
      continue
    fi
    echo "HypoPG payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv /tmp/first/postgresql /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
cp -a "$extroot/." "$pgroot/"
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" \
  --archive "/input/$pg_archive" --archive "/extension/$hypopg_archive" \
  --report "/analysis/hypopg.json"
useradd -m postgres
chown postgres:postgres /tmp/data /tmp/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -l /tmp/data/server.log -o '-k /tmp/socket -p 55432 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55432 -d postgres -f /work/probe.sql | tee /tmp/probe.out
grep -Eq 'Index Scan using .*btree_hypo_probe_id' /tmp/probe.out
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
echo 'PASS: relocated PostgreSQL and HypoPG archives on clean Alpine 3.22'
