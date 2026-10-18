#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
extension_version=5.5.0
architecture=x86_64
extension_archive="pg_partman-${extension_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
core_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /extension
sha256sum -c pg_partman.sha256
cd /core
sha256sum -c "$core_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/ext /tmp/data /tmp/socket
tar -xzf "/core/$core_archive" -C /tmp/first
tar -xzf "/extension/$extension_archive" -C /tmp/ext
pgroot=/tmp/first/postgresql
extroot=/tmp/ext/pg_partman
python3 - "$extension_archive" "$pg_version" <<'PY'
import json, pathlib, sys, tarfile
archive, pg = sys.argv[1:]
with tarfile.open('/extension/' + archive, 'r:gz') as package:
    members = package.getmembers()
    names = {member.name for member in members}
    assert {name.split('/')[0] for name in names} == {'pg_partman', 'metadata.json'}
    assert not any(member.issym() or member.islnk() for member in members)
    metadata = json.load(package.extractfile('metadata.json'))
    assert metadata['project'] == 'pg_partman'
    assert metadata['version'] == '5.5.0'
    assert metadata['sql_names'] == ['pg_partman']
    assert metadata['postgresql_version'] == pg
    assert metadata['platform'] == 'linux' and metadata['architecture'] == 'x86_64'
    assert metadata['release_eligible'] is False
root = pathlib.Path('/tmp/ext/pg_partman')
assert (root / 'lib/pg_partman_bgw.so').is_file()
assert (root / 'share/extension/pg_partman.control').is_file()
assert (root / 'share/extension/pg_partman--5.5.0.sql').is_file()
assert (root / 'LICENSES/pg_partman/LICENSE.txt').is_file()
PY
while IFS= read -r -d '' source; do
  rel=${source#"$extroot/"}
  destination="$pgroot/$rel"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
    echo "pg_partman payload collision: $rel" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
cp -a "$extroot/." "$pgroot/"
useradd -m postgres
chown -R postgres:postgres /tmp/first /tmp/data /tmp/socket /tmp/moved
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -o '-k /tmp/socket -p 55432 -h ""' -w start
stop_server() { runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true; }
trap stop_server EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55432 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
runuser -u postgres -- mv "$pgroot" /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture x86_64 \
  --archive "/core/$core_archive" --archive "/extension/$extension_archive" \
  --report /analysis/pg_partman.json
mkdir -p /tmp/moved-data /tmp/moved-socket
chown postgres:postgres /tmp/moved-data /tmp/moved-socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/moved-data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -o '-k /tmp/moved-socket -p 55433 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/moved-socket -p 55433 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -m fast -w stop
trap - EXIT
echo "PASS: pg_partman $extension_version on relocated PostgreSQL $pg_version in Alpine 3.22"
