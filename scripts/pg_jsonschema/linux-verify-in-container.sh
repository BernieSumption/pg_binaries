#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
extension_version=0.3.4
extension_commit=cbe74b570d38aa0c4d42914e7a118bcb3adaee7a
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture:$(uname -m)" in x86_64:x86_64|arm64:aarch64) ;; *) echo "Architecture mismatch" >&2; exit 2 ;; esac
archive="pg_jsonschema-${extension_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
core_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /extension
sha256sum -c "$archive.sha256"
cd /core
sha256sum -c "$core_archive.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/extension /tmp/data /tmp/socket
tar -xzf "/core/$core_archive" -C /tmp/first
tar -xzf "/extension/$archive" -C /tmp/extension
useradd -m postgres
chown -R postgres:postgres /tmp/first /tmp/moved
pgroot=/tmp/first/postgresql
test "$("$pgroot/bin/postgres" --version)" = "postgres (PostgreSQL) $pg_version"
python3 - "/extension/$archive" "$extension_commit" "$architecture" "$pg_version" "$extension_version" <<'PY'
import json, pathlib, sys
import tarfile
archive, commit, architecture, pg_version, version = sys.argv[1:]
with tarfile.open(archive, 'r:gz') as package:
    members = package.getmembers()
    names = {member.name for member in members}
    assert {name.split('/')[0] for name in names} == {'pg_jsonschema', 'metadata.json'}
    assert 'metadata.json' in names
    metadata = json.load(package.extractfile('metadata.json'))
    assert metadata == {
        'project': 'pg_jsonschema', 'version': version, 'sql_names': ['pg_jsonschema'],
        'requires': [], 'configuration_prerequisites': [], 'runtime_prerequisites': [],
        'postgresql_version': pg_version, 'platform': 'linux', 'architecture': architecture,
        'source': {'url': 'https://github.com/supabase/pg_jsonschema.git', 'commit': commit,
                   'cargo_lock_sha256': 'ab865dc25d9eea4bf7dbfaf8fae13283e5c0bce4bca460fe10464c6716e67028'},
        'release_eligible': False, 'redistribution_status': 'postgresql-core-redistribution-review-pending',
    }, metadata
    assert not any(member.issym() or member.islnk() for member in members)
root = pathlib.Path('/tmp/extension/pg_jsonschema')
assert (root / 'lib/pg_jsonschema.so').is_file()
assert (root / 'share/extension/pg_jsonschema.control').is_file()
assert (root / 'LICENSES/cargo/cargo-license-inventory.json').is_file()
(pathlib.Path('/analysis/source-identity.txt')).write_text(
    f'pg_jsonschema_commit={commit}\n')
PY
extroot=/tmp/extension/pg_jsonschema
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
    echo "pg_jsonschema payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
cp -a "$extroot/." "$pgroot/"
chown -R postgres:postgres /tmp/first
chown postgres:postgres /tmp/data /tmp/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -o '-k /tmp/socket -p 55432 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55432 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT
runuser -u postgres -- mv "$pgroot" /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" \
  --archive "/core/$core_archive" --archive "/extension/$archive" --report /analysis/pg_jsonschema.json
mkdir -p /tmp/moved-data /tmp/moved-socket
chown postgres:postgres /tmp/moved-data /tmp/moved-socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/moved-data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -o '-k /tmp/moved-socket -p 55433 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/moved-socket -p 55433 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -m fast -w stop
trap - EXIT
echo "PASS: pg_jsonschema $extension_version on relocated PostgreSQL $pg_version in Alpine 3.22"
