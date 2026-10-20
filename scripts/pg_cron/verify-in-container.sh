#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
version=1.6.8
source_url='https://github.com/citusdata/pg_cron/archive/refs/tags/v1.6.8.tar.gz'
source_sha256='c19ab9bb35406c60fb51ecda993737c083850abe424acb6c1030439d00a1f8e4'
pg_version=${PG_VERSION:-18.6}
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
extension_archive="pg_cron-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
core_sha256=$(sha256sum "$pg_archive" | awk '{print $1}')
cd /extension
sha256sum -c "$extension_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/extension /tmp/data /tmp/socket
tar -xzf "/input/$pg_archive" -C /tmp/first
tar -xzf "/extension/$extension_archive" -C /tmp/extension
pgroot=/tmp/first/postgresql
extroot=/tmp/extension/pg_cron
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
python3 - "$extroot" "$source_url" "$architecture" "$source_sha256" "$pg_version" "$pg_archive" "$core_sha256" <<'PY'
import json, sys
from pathlib import Path
root=Path(sys.argv[1]).parent
metadata=json.loads((root/'metadata.json').read_text())
if metadata != {'project':'pg_cron','version':'1.6.8','sql_names':['pg_cron'],'requires':[],
 'configuration_prerequisites':[{'type':'postgresql_setting','name':'shared_preload_libraries','value':'pg_cron'},
                                {'type':'postgresql_setting','name':'cron.use_background_workers','value':'on'}],
 'runtime_prerequisites':[],'postgresql_version':sys.argv[5],
 'core_archive':{'basename':sys.argv[6],'sha256':sys.argv[7]},
 'platform':'linux','architecture':sys.argv[3],
 'source':{'url':sys.argv[2],'sha256':sys.argv[4]}}:
 raise SystemExit('pg_cron package metadata mismatch')
inv=json.loads((root/'pg_cron/LICENSES/pg_cron-inventory.json').read_text())
if inv.get('schema_version')!=1 or len(inv.get('components',[]))!=1: raise SystemExit('invalid licence inventory')
c=inv['components'][0]
for k,v in {'component':'pg_cron','version':'1.6.8','payload_paths':['lib/pg_cron.so','share/extension'],
            'license_file':'pg_cron.txt','source_url':sys.argv[2],'source_sha256':sys.argv[4]}.items():
 if c.get(k)!=v: raise SystemExit(f'licence inventory {k} mismatch')
r=c.get('redistribution_review',{})
if r.get('status')!='resolved' or r.get('source_obligation')!='none' or not r.get('basis'): raise SystemExit('redistribution review is incomplete')
license=(root/'pg_cron/LICENSES/pg_cron.txt').read_text()
for text in ('Permission to use, copy, modify, and distribute this software','provided that the above copyright notice and this','CITUS DATA SPECIFICALLY DISCLAIMS ANY WARRANTIES'):
 if text not in license: raise SystemExit('upstream licence notice incomplete')
if {p.stem for p in (root/'pg_cron/share/extension').glob('*.control')}!={'pg_cron'}: raise SystemExit('unexpected SQL extensions')
if not (root/'pg_cron/lib/pg_cron.so').is_file(): raise SystemExit('missing pg_cron.so')
if {p.name for p in root.iterdir()}!={'pg_cron','metadata.json'}: raise SystemExit('unexpected package archive members')
PY
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}; destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
    echo "pg_cron payload collision: $relative" >&2; exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv /tmp/first/postgresql /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
cp -a "$extroot/." "$pgroot/"
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" --archive "/input/$pg_archive" --archive "/extension/$extension_archive" --report "/analysis/pg_cron.json"
useradd -m postgres
chown postgres:postgres /tmp/data /tmp/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -l /tmp/data/server.log -o "-k /tmp/socket -p 55432 -h '' -c shared_preload_libraries=pg_cron -c cron.use_background_workers=on -c max_worker_processes=20 -c cron.database_name=postgres" -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true' EXIT
psql=("$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55432 -d postgres)
runuser -u postgres -- "${psql[@]}" -c 'CREATE EXTENSION pg_cron; CREATE TABLE public.pg_cron_probe (ran_at timestamptz NOT NULL);'
job_id=$(runuser -u postgres -- "${psql[@]}" -Atc "SELECT cron.schedule('feasibility-probe', '* * * * *', 'INSERT INTO public.pg_cron_probe VALUES (clock_timestamp())')")
[[ $job_id =~ ^[0-9]+$ ]]
deadline=$((SECONDS + 150))
while (( SECONDS < deadline )); do
  count=$(runuser -u postgres -- "${psql[@]}" -Atc 'SELECT count(*) FROM public.pg_cron_probe')
  if [[ $count =~ ^[0-9]+$ ]] && (( count > 0 )); then break; fi
  sleep 2
done
if [[ ! ${count:-0} =~ ^[0-9]+$ ]] || (( count < 1 )); then
  cat /tmp/data/server.log >&2
  echo 'pg_cron did not execute the scheduled command before timeout' >&2
  exit 1
fi
runuser -u postgres -- "${psql[@]}" -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM cron.job_run_details WHERE jobid = $job_id AND status = 'succeeded') THEN RAISE EXCEPTION 'no successful background-worker job run'; END IF; END \$\$; SELECT cron.unschedule($job_id);"
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
echo "PASS: relocated PostgreSQL $pg_version and pg_cron $version installed and executed a scheduled job using a background worker on Alpine 3.22"
