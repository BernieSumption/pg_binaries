#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
if [[ ! $pg_version =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Unsupported PostgreSQL version: $pg_version" >&2; exit 2
fi
version=1.16
source_url='https://github.com/sraoss/pg_ivm/archive/refs/tags/v1.16.tar.gz'
source_sha256='87807d6af1974fce591715d55f75d939dffea33ea6908b413e62d3dd79b9c583'
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
extension_archive="pg_ivm-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
cd /extension
sha256sum -c "$extension_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/extension /tmp/data /tmp/socket
tar -xzf "/input/$pg_archive" -C /tmp/first
tar -xzf "/extension/$extension_archive" -C /tmp/extension
pgroot=/tmp/first/postgresql
extroot=/tmp/extension/pg_ivm
core_sha256=$(sha256sum "/input/$pg_archive" | awk '{print $1}')
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
python3 - "$extroot" "$source_url" "$architecture" "$source_sha256" "$pg_version" "$pg_archive" "$core_sha256" <<'PY'
import json, os, sys
from pathlib import Path
root=Path(sys.argv[1]).parent
metadata=json.loads((root/'metadata.json').read_text())
if metadata != {'project':'pg_ivm','version':'1.16','sql_names':['pg_ivm'],'requires':[],
 'configuration_prerequisites':[{'type':'postgresql_setting','name':'shared_preload_libraries','value':'pg_ivm'}],
 'runtime_prerequisites':[],'postgresql_version':sys.argv[5],'platform':'linux','architecture':sys.argv[3],
 'source':{'url':sys.argv[2],'sha256':sys.argv[4]},
 'core_archive':{'basename':sys.argv[6],'sha256':sys.argv[7]}}:
 raise SystemExit('pg_ivm package metadata mismatch')
digest=metadata['source']['sha256']
if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest): raise SystemExit('invalid source SHA-256')
inv=json.loads((root/'pg_ivm/LICENSES/pg_ivm-inventory.json').read_text())
if inv.get('schema_version')!=1 or len(inv.get('components',[]))!=1: raise SystemExit('invalid licence inventory')
c=inv['components'][0]
for k,v in {'component':'pg_ivm','version':'1.16','payload_paths':['lib/pg_ivm.so','share/extension','bin/pg_ivm_dump_metadata'],'license_file':'pg_ivm.txt','source_url':sys.argv[2],'source_sha256':digest}.items():
 if c.get(k)!=v: raise SystemExit(f'licence inventory {k} mismatch')
r=c.get('redistribution_review',{})
if r.get('status')!='resolved' or not r.get('basis') or r.get('source_obligation')!='none': raise SystemExit('redistribution review incomplete')
license=(root/'pg_ivm/LICENSES/pg_ivm.txt').read_text()
for text in ('Permission to use, copy, modify, and distribute this software','provided that the above copyright notice and this','THE AUTHORS SPECIFICALLY DISCLAIM ANY WARRANTIES'):
 if text not in license: raise SystemExit('upstream licence notice incomplete')
if {p.stem for p in (root/'pg_ivm/share/extension').glob('*.control')}!={'pg_ivm'}: raise SystemExit('unexpected SQL extensions')
for p in ('lib/pg_ivm.so','bin/pg_ivm_dump_metadata'):
 if not (root/'pg_ivm'/p).is_file(): raise SystemExit(f'missing {p}')
if {p.name for p in root.iterdir()}!={'pg_ivm','metadata.json'}: raise SystemExit('unexpected package archive members')
PY
test -s "$extroot/LICENSES/pg_ivm.txt"
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}; destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
    echo "pg_ivm payload collision: $relative" >&2; exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv /tmp/first/postgresql /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
cp -a "$extroot/." "$pgroot/"
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" --archive "/input/$pg_archive" --archive "/extension/$extension_archive" --report "/analysis/pg_ivm.json"
useradd -m postgres
chown postgres:postgres /tmp/data /tmp/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -l /tmp/data/server.log -o "-k /tmp/socket -p 55432 -h '' -c shared_preload_libraries=pg_ivm" -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55432 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
echo "PASS: relocated PostgreSQL $pg_version and pg_ivm 1.16 archives on clean Alpine 3.22"
