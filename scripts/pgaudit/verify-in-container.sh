#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
case "$pg_version" in
  15.19) version=1.7.1; source_url='https://api.github.com/repos/pgaudit/pgaudit/tarball/72da89c3fa02f3f2b9f3933214d91ad9c3428467'; source_sha256=1e52448238908a09e0e78b3375dcefbfca51509fdbb3a4d92eb710e380ed3567 ;;
  16.15) version=16.1; source_url='https://api.github.com/repos/pgaudit/pgaudit/tarball/a81792e8a4ea8f7aaf75bd610fcc4c2f96650bdc'; source_sha256=b0648fcebe5a67340c406126e6dddc703fd03821a9ace80390e128a0d1c91c73 ;;
  17.11) version=17.1; source_url='https://api.github.com/repos/pgaudit/pgaudit/tarball/538f89a93d8fd0d8913f3d740cacaea7b7eb66d9'; source_sha256=20e980bd0c22b4ae33305ec2b774bd846bf343642adad108b6c28b422a648312 ;;
  18.6) version=18.0; source_url='https://github.com/pgaudit/pgaudit/archive/refs/tags/18.0.tar.gz'; source_sha256=988e8afeda320ebe0a3e632ef6b6bce5d3a08346c2e100a173a585c9521d1fa5 ;;
  *) echo "Unsupported PostgreSQL version for pgAudit: $pg_version" >&2; exit 2 ;;
esac
export PGAUDIT_VERSION="$version" PGAUDIT_SOURCE_URL="$source_url" PGAUDIT_SOURCE_SHA256="$source_sha256"
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
extension_archive="pgaudit-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
cd /extension
sha256sum -c "$extension_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/extension /tmp/data /tmp/socket
tar -xzf "/input/$pg_archive" -C /tmp/first
tar -xzf "/extension/$extension_archive" -C /tmp/extension
pgroot=/tmp/first/postgresql
extroot=/tmp/extension/pgaudit
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
test -s "$extroot/LICENSES/pgAudit.txt"
python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path('/tmp/extension')
metadata = json.loads((root / 'metadata.json').read_text())
expected = {
    'project': 'pgaudit', 'version': os.environ['PGAUDIT_VERSION'], 'sql_names': ['pgaudit'],
    'requires': [],
    'configuration_prerequisites': [{
        'type': 'postgresql_setting', 'name': 'shared_preload_libraries',
        'value': 'pgaudit',
    }],
    'runtime_prerequisites': [], 'postgresql_version': os.environ['PG_VERSION'],
    'platform': 'linux', 'architecture': __import__('os').environ['PG_ARCHITECTURE'],
    'source': {
        'url': os.environ['PGAUDIT_SOURCE_URL'],
        'sha256': os.environ['PGAUDIT_SOURCE_SHA256'],
    },
}
if metadata != expected:
    raise SystemExit(f'pgAudit package metadata mismatch: {metadata!r}')
inventory = json.loads((root / 'pgaudit/LICENSES/pgaudit-inventory.json').read_text())
if inventory.get('schema_version') != 1 or len(inventory.get('components', [])) != 1:
    raise SystemExit('pgAudit licence inventory must contain one component')
component = inventory['components'][0]
for key, value in {
    'component': 'pgaudit', 'version': expected['version'],
    'payload_paths': ['lib/pgaudit.so', 'share/extension'],
    'license_file': 'pgAudit.txt',
    'source_url': expected['source']['url'],
    'source_sha256': expected['source']['sha256'],
}.items():
    if component.get(key) != value:
        raise SystemExit(f'pgAudit licence inventory {key} mismatch')
review = component.get('redistribution_review', {})
if review.get('status') != 'resolved' or not review.get('basis') or review.get('source_obligation') != 'none':
    raise SystemExit('pgAudit redistribution review is incomplete')
license_text = (root / 'pgaudit/LICENSES/pgAudit.txt').read_text()
for fragment in ('This code is released under the PostgreSQL licence',
                 'Permission to use, copy, modify, and distribute this software'):
    if fragment not in license_text:
        raise SystemExit(f'pgAudit upstream licence text is incomplete: {fragment}')
if {p.stem for p in (root / 'pgaudit/share/extension').glob('*.control')} != {'pgaudit'}:
    raise SystemExit('pgAudit payload must contain exactly the pgaudit SQL extension')
control = (root / 'pgaudit/share/extension/pgaudit.control').read_text()
if f"default_version = '{expected['version']}'" not in control.splitlines():
    raise SystemExit('pgAudit control file does not declare the selected release')
if not (root / 'pgaudit/lib/pgaudit.so').is_file():
    raise SystemExit('pgAudit shared library missing from payload')
if {p.name for p in root.iterdir()} != {'pgaudit', 'metadata.json'}:
    raise SystemExit('pgAudit archive must contain payload and sibling metadata.json only')
PY
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then
      continue
    fi
    echo "pgAudit payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv /tmp/first/postgresql /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
cp -a "$extroot/." "$pgroot/"
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" \
  --archive "/input/$pg_archive" --archive "/extension/$extension_archive" \
  --report "/analysis/pgaudit.json"
useradd -m postgres
chown postgres:postgres /tmp/data /tmp/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -l /tmp/data/server.log \
  -o "-k /tmp/socket -p 55432 -h '' -c shared_preload_libraries=pgaudit -c logging_collector=on -c log_directory=log -c log_filename=pgaudit.log" -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true' EXIT
probe_output=$(runuser -u postgres -- "$pgroot/bin/psql" -X -A -t -v ON_ERROR_STOP=1 \
  -h /tmp/socket -p 55432 -d postgres -f /work/probe.sql)
grep -Fxq 'audit payload' <<< "$probe_output"
log_file=/tmp/data/log/pgaudit.log
test -s "$log_file"
grep -F 'AUDIT: SESSION' "$log_file" >/dev/null
grep -F 'DDL' "$log_file" | grep -F 'CREATE TABLE public.pgaudit_probe' >/dev/null
grep -F 'WRITE' "$log_file" | grep -F 'INSERT INTO public.pgaudit_probe' >/dev/null
grep -F 'READ' "$log_file" | grep -F 'SELECT payload FROM public.pgaudit_probe' >/dev/null
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
echo "PASS: relocated PostgreSQL $pg_version and pgAudit $version archives on clean Alpine 3.22"
