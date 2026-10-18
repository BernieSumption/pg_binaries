#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
extension_version=0.3.4
extension_commit=cbe74b570d38aa0c4d42914e7a118bcb3adaee7a
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture:$(uname -m)" in x86_64:x86_64|arm64:aarch64) ;; *) echo "Architecture mismatch" >&2; exit 2 ;; esac
archive="pg_jsonschema-${extension_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /archives
sha256sum -c "$archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/data /tmp/socket
tar -xzf "$archive" -C /tmp/first
useradd -m postgres
chown -R postgres:postgres /tmp/first /tmp/moved
pgroot=/tmp/first/postgresql
test "$("$pgroot/bin/postgres" --version)" = "postgres (PostgreSQL) $pg_version"
python3 - "$pgroot" "$extension_commit" "$architecture" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / 'manifest.json').read_text())
assert manifest['version'] == '18.6' and manifest['architecture'] == sys.argv[3], manifest
assert (root / 'lib/pg_jsonschema.so').is_file()
assert (root / 'share/extension/pg_jsonschema.control').is_file()
(pathlib.Path('/analysis/source-identity.txt')).write_text(
    f'pg_jsonschema_commit={sys.argv[2]}\n')
PY
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" \
  --archive "/archives/$archive" --report /analysis/pg_jsonschema.json
chown postgres:postgres /tmp/data /tmp/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -o '-k /tmp/socket -p 55432 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55432 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
runuser -u postgres -- mv "$pgroot" /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
mkdir -p /tmp/moved-data /tmp/moved-socket
chown postgres:postgres /tmp/moved-data /tmp/moved-socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/moved-data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -o '-k /tmp/moved-socket -p 55433 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/moved-socket -p 55433 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -m fast -w stop
trap - EXIT
echo "PASS: pg_jsonschema $extension_version on relocated PostgreSQL $pg_version in Alpine 3.22"
