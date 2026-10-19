#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
extension_version=3.7.0
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture:$(uname -m)" in x86_64:x86_64|arm64:aarch64) ;; *) echo "Architecture mismatch" >&2; exit 2 ;; esac
archive="address-standardizer-${extension_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
core_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /core
sha256sum -c "$core_archive.sha256"
cd /archives
sha256sum -c "$archive.sha256"
mkdir -p /tmp/first /tmp/extension /tmp/data /tmp/socket
tar -xzf "/core/$core_archive" -C /tmp/first
tar -xzf "$archive" -C /tmp/extension
pgroot=/tmp/first/postgresql
extroot=/tmp/extension/address_standardizer
test "$("$pgroot/bin/postgres" --version)" = "postgres (PostgreSQL) $pg_version"
python3 - "$pgroot" "$extroot" /tmp/extension/metadata.json "$architecture" "$pg_version" <<'PY'
import json, pathlib, sys
import subprocess
root, payload, metadata_path = map(pathlib.Path, sys.argv[1:4])
metadata = json.loads(metadata_path.read_text())
configured_pkglibdir = pathlib.Path(subprocess.check_output([str(root / 'bin/pg_config'), '--pkglibdir'], text=True).strip())
module_rel = configured_pkglibdir.relative_to(root)
assert metadata == {
    'project': 'Address Standardizer', 'version': '3.7.0',
    'sql_names': ['address_standardizer', 'address_standardizer_data_us'], 'requires': [],
    'configuration_prerequisites': [], 'runtime_prerequisites': [],
    'postgresql_version': sys.argv[5], 'platform': 'linux', 'architecture': sys.argv[4],
    'payload_paths': [f'address_standardizer/{module_rel}/address_standardizer.so',
                      'address_standardizer/lib/libpcre2-8.so', 'address_standardizer/share/extension',
                      'address_standardizer/LICENSES'],
    'source': {'url': 'https://github.com/postgis/address_standardizer/tree/v3.7.0',
               'commit': 'fa11ff53eb49b863d9ffff37f6afd5ff9299c581'},
    'dependencies': [{'name': 'PCRE2', 'version': '10.48',
                      'sha256': 'b6c68fdf6f3ac31388b50aa89ff0fc49c00c987c16e7b5146491d12003f2c8ed'}],
    'license_inventory': 'address_standardizer/LICENSES/license-inventory.json'
}
assert {p.name for p in pathlib.Path('/tmp/extension').iterdir()} == {'address_standardizer', 'metadata.json'}
assert metadata['version'] == '3.7.0' and metadata['architecture'] == sys.argv[4]
assert metadata['sql_names'] == ['address_standardizer', 'address_standardizer_data_us']
assert (payload / module_rel / 'address_standardizer.so').is_file()
for name in metadata['sql_names']:
    assert (payload / f'share/extension/{name}.control').is_file()
assert (payload / 'share/extension/address_standardizer_data_us--3.7.sql').is_file()
assert (payload / 'lib/libpcre2-8.so').exists()
inventory = json.loads((payload / 'LICENSES/license-inventory.json').read_text())
assert inventory['schema_version'] == 1 and len(inventory['components']) == 2
assert (payload / 'LICENSES/Address-Standardizer.txt').is_file()
assert (payload / 'LICENSES/PCRE2.txt').is_file()
PY
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
    echo "Address Standardizer payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
cp -a "$extroot/." "$pgroot/"
python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" \
  --archive "/core/$core_archive" --archive "/archives/$archive" --report /analysis/address-standardizer.json
useradd -m postgres
mkdir -p /tmp/moved /tmp/moved-data /tmp/moved-socket
chown -R postgres:postgres /tmp/first /tmp/moved /tmp/data /tmp/socket /tmp/moved-data /tmp/moved-socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -o '-k /tmp/socket -p 55432 -h ""' -w start
stop_server() { runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m immediate stop >/dev/null 2>&1 || true; }
trap stop_server EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/socket -p 55432 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/data -m fast -w stop
trap - EXIT

runuser -u postgres -- mv "$pgroot" /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/moved-data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -o '-k /tmp/moved-socket -p 55433 -h ""' -w start
stop_server() { runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -m immediate stop >/dev/null 2>&1 || true; }
trap stop_server EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/moved-socket -p 55433 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/moved-data -m fast -w stop
trap - EXIT
echo "PASS: Address Standardizer $extension_version with PostgreSQL $pg_version on relocated Alpine 3.22"
