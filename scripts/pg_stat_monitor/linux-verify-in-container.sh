#!/usr/bin/env bash
set -euo pipefail
pg_version=18.6
version=2.4.0
project=pg_stat_monitor
core_archive="postgresql-${pg_version}-linux-x86_64.tar.gz"
extension_archive="${project}-${version}-postgresql-${pg_version}-linux-x86_64.tar.gz"
cd /core
sha256sum -c "$core_archive.sha256"
cd /extension
sha256sum -c "${project}.sha256"
test -f "/core/$core_archive" && test -f "/extension/$extension_archive"
mkdir -p /tmp/first /tmp/moved /tmp/ext /tmp/data /tmp/socket
python3 - "$extension_archive" <<'PY'
import json, pathlib, re, sys, tarfile
archive = pathlib.Path('/extension') / sys.argv[1]
with tarfile.open(archive, 'r:gz') as package:
    members = package.getmembers()
    names = [member.name for member in members]
    if len(names) != len(set(names)) or not names:
        raise SystemExit('duplicate or empty extension archive members')
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if (path.is_absolute() or '..' in path.parts or not path.parts
                or path.parts[0] not in {'pg_stat_monitor', 'metadata.json'}
                or member.issym() or member.islnk() or not (member.isfile() or member.isdir())):
            raise SystemExit(f'unsafe extension archive member: {member.name}')
    if names.count('metadata.json') != 1:
        raise SystemExit('missing package metadata')
    metadata = json.load(package.extractfile('metadata.json'))
    expected = {
        'project': 'pg_stat_monitor', 'version': '2.4.0',
        'sql_names': ['pg_stat_monitor'], 'requires': [],
        'configuration_prerequisites': [
            {'type': 'postgresql_setting', 'name': 'shared_preload_libraries', 'value': 'pg_stat_monitor'}],
        'runtime_prerequisites': [], 'postgresql_version': '18.6',
        'platform': 'linux', 'architecture': 'x86_64', 'release_eligible': False,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise SystemExit(f'package metadata {key} mismatch')
    source = metadata.get('source_archive')
    if (not isinstance(source, dict) or not source.get('url')
            or not isinstance(source.get('sha256'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', source['sha256'])):
        raise SystemExit('package source identity is incomplete')
PY
tar -xzf "/core/$core_archive" -C /tmp/first
tar -xzf "/extension/$extension_archive" -C /tmp/ext
pgroot=/tmp/first/postgresql
extroot=/tmp/ext/pg_stat_monitor
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
test -f "$extroot/lib/pg_stat_monitor.so"
test -f "$extroot/share/extension/pg_stat_monitor.control"
test -f "$extroot/LICENSES/pg_stat_monitor/LICENSE"
find "$extroot/share/extension" -maxdepth 1 -name 'pg_stat_monitor--*.sql' -print -quit | grep -q .
while IFS= read -r -d '' source; do
  rel=${source#"$extroot/"}
  destination="$pgroot/$rel"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
    echo "pg_stat_monitor payload collision: $rel" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv "$pgroot" /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
cp -a "$extroot/." "$pgroot/"
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture x86_64 \
  --archive "/core/$core_archive" --archive "/extension/$extension_archive" \
  --report /analysis/pg_stat_monitor.json
useradd -m postgres
chown -R postgres:postgres /tmp/data /tmp/socket /tmp/moved
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
if ! runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -l /tmp/data/server.log \
    -o '-k /tmp/socket -p 55432 -h "" -c shared_preload_libraries=pg_stat_monitor' -w start; then
  cat /tmp/data/server.log >&2
  exit 1
fi
stop_server() { runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true; }
trap stop_server EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55432 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
echo "PASS: pg_stat_monitor $version on relocated PostgreSQL $pg_version in Alpine 3.22"
