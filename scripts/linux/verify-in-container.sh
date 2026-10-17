#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
case "$architecture:$(uname -m)" in
  x86_64:x86_64|arm64:aarch64) ;;
  *) echo "Verifier container architecture does not match $architecture: $(uname -m)" >&2; exit 2 ;;
esac
if [[ ! $pg_version =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Linux pilot currently supports PostgreSQL 15 through 18 minors only: $pg_version" >&2
  exit 2
fi
pg="postgresql-${pg_version}-linux-${architecture}.tar.gz"
vector="pgvector-0.8.7-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /out
sha256sum -c "$pg.sha256" "$vector.sha256"
mkdir -p /tmp/first /tmp/moved /tmp/vector
tar -xzf "$pg" -C /tmp/first
tar -xzf "$vector" -C /tmp/vector
python3 - "$pg_version" "$architecture" <<'PY'
import json
from pathlib import Path
import re
import sys
version = sys.argv[1]
architecture = sys.argv[2]
with open('/tmp/first/postgresql/manifest.json') as f:
    m = json.load(f)
assert (m['schema_version'], m['component'], m['version'],
        m['postgresql_version'], m['platform'], m['architecture']) == (
            1, 'postgresql', version, version, 'linux', architecture), m
controls = {path.stem for path in Path('/tmp/first/postgresql/share/extension').glob('*.control')}
assert controls and m['included_extensions'] == sorted(controls), m
assert 'vector' not in controls, controls

root = Path('/tmp/first/postgresql')
license_dir = root / 'LICENSES'
inventory = json.loads((license_dir / 'inventory.json').read_text())
assert inventory['schema_version'] == 1, inventory
components = inventory['components']
postgresql = [entry for entry in components if entry['component'] == 'postgresql']
assert len(postgresql) == 1, components
postgresql = postgresql[0]
assert postgresql['version'] == version, postgresql
assert postgresql['payload_paths'] == ['bin', 'include', 'lib', 'libexec', 'share'], postgresql
assert postgresql['license_file'] == 'PostgreSQL.txt', postgresql
assert postgresql['license_source'] == f'https://ftp.postgresql.org/pub/source/v{version}/postgresql-{version}.tar.bz2', postgresql
assert all((root / path).is_dir() for path in postgresql['payload_paths']), postgresql
postgres_license = license_dir / postgresql['license_file']
assert postgres_license.is_file() and postgres_license.stat().st_size > 0, postgresql

runtime = [entry for entry in components if entry['component'] == 'runtime-package']
assert runtime, components
assert len(components) == len(runtime) + 1, components
assert all(entry['package'] and entry['version'] for entry in runtime), runtime
assert len({entry['package'] for entry in runtime}) == len(runtime), runtime
glibc = next(entry for entry in runtime if entry['package'] == 'libc6')
assert m['bundled_glibc_version'] == glibc['version'], (m, glibc)
assert glibc['source_package'] == 'glibc' and glibc['source_version'] == glibc['version'], glibc
assert len(glibc['source_urls']) == 3 and all(url.startswith('https://archive.ubuntu.com/ubuntu/pool/main/g/glibc/') for url in glibc['source_urls']), glibc
for filename in glibc['additional_license_files']:
    assert (license_dir / filename).is_file() and (license_dir / filename).stat().st_size > 0, filename
musl = next(entry for entry in runtime if entry['package'] == 'musl')
assert musl['source_package'] == 'musl' and musl['source_version'] == musl['version'], musl
assert len(musl['source_urls']) == 3 and all(url.startswith('https://archive.ubuntu.com/ubuntu/pool/universe/m/musl/') for url in musl['source_urls']), musl
mapped = []
for entry in runtime:
    assert entry['license_source'] == f"https://packages.ubuntu.com/jammy/{entry['package']}", entry
    assert Path(entry['license_file']).name == entry['license_file'], entry
    license_path = license_dir / entry['license_file']
    assert license_path.is_file() and license_path.stat().st_size > 0, entry
    for name in re.findall(r'/usr/share/common-licenses/([A-Za-z0-9.+-]+)',
                           license_path.read_text(encoding='utf-8', errors='replace')):
        common = license_dir / 'common-licenses' / name.rstrip('.,;:')
        assert common.is_file() and common.stat().st_size > 0, common
    assert entry['payload_paths'], entry
    for relative in entry['payload_paths']:
        relative_path = Path(relative)
        assert not relative_path.is_absolute() and '..' not in relative_path.parts, (entry, relative)
        payload = root / relative
        assert payload.is_file() and payload.stat().st_size > 0, (entry, relative)
        mapped.append(relative)
actual = sorted(path.relative_to(root).as_posix()
                for directory in ('lib/runtime', 'lib/glibc')
                for path in (root / directory).iterdir() if path.is_file())
actual.append('bin/.pg-launcher')
assert sorted(mapped) == sorted(actual), {'mapped': sorted(mapped), 'actual': sorted(actual)}
wrappers = {path.name for path in (root / 'bin').iterdir()
            if path.is_file() and not path.is_symlink() and path.name != '.pg-launcher'}
payloads = {path.name for path in (root / 'libexec').iterdir()}
assert wrappers == payloads, (wrappers, payloads)
launcher = root / 'bin/.pg-launcher'
assert launcher.read_bytes().startswith(b'\x7fELF'), launcher
assert all((root / 'bin' / name).stat().st_ino == launcher.stat().st_ino for name in wrappers)

with open('/tmp/vector/metadata.json') as f:
    m = json.load(f)
assert m == {
    'project': 'pgvector',
    'version': '0.8.7',
    'sql_names': ['vector'],
    'requires': [],
    'configuration_prerequisites': [],
    'runtime_prerequisites': [],
}, m
PY
test -s /tmp/vector/pgvector/LICENSES/pgvector.txt
pgroot=/tmp/first/postgresql
extroot=/tmp/vector/pgvector
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then
      continue
    fi
    echo "Extension payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
cp -a "$extroot/." "$pgroot/"
test -s "$pgroot/LICENSES/pgvector.txt"
python3 /usr/local/bin/check-elf-dependencies "$pgroot"
test "$(/tmp/first/postgresql/bin/postgres --version)" = "postgres (PostgreSQL) $pg_version"
useradd -m postgres
mkdir -p /tmp/first-data /tmp/first-socket
chown postgres:postgres /tmp/first-data /tmp/first-socket
runuser -u postgres -- /tmp/first/postgresql/bin/initdb -D /tmp/first-data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- /tmp/first/postgresql/bin/pg_ctl -D /tmp/first-data -o '-k /tmp/first-socket -p 55430 -h ""' -w start
trap 'runuser -u postgres -- /tmp/first/postgresql/bin/pg_ctl -D /tmp/first-data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- /tmp/first/postgresql/bin/psql -XAt -h /tmp/first-socket -p 55430 -d postgres -c 'SHOW server_version' | grep -Fx "$pg_version"
runuser -u postgres -- /tmp/first/postgresql/bin/psql -X -v ON_ERROR_STOP=1 -h /tmp/first-socket -p 55430 -d postgres <<'SQL'
CREATE EXTENSION vector;
CREATE TABLE relocation_probe (embedding vector(3));
INSERT INTO relocation_probe VALUES ('[1,0,0]');
DO $$ BEGIN IF (SELECT embedding <-> '[1,0,0]'::vector FROM relocation_probe) <> 0 THEN
  RAISE EXCEPTION 'pgvector smoke test failed'; END IF; END $$;
SQL
runuser -u postgres -- /tmp/first/postgresql/bin/pg_ctl -D /tmp/first-data -m fast -w stop
trap - EXIT
mv /tmp/first/postgresql /tmp/moved/postgresql
pgroot=/tmp/moved/postgresql
mkdir -p /tmp/pgdata /tmp/pgsocket
chown postgres:postgres /tmp/pgdata /tmp/pgsocket
runuser -u postgres -- "$pgroot/bin/initdb" -D /tmp/pgdata --encoding=UTF8 --locale=C --no-instructions
mkdir -p /tmp/pilot-tls
openssl req -x509 -newkey rsa:2048 -sha256 -days 1 -nodes -subj '/CN=pilot-ca' -keyout /tmp/pilot-tls/ca.key -out /tmp/pilot-tls/ca.crt >/dev/null 2>&1
for peer in server client; do
  if [[ $peer == server ]]; then cn=localhost; else cn=postgres; fi
  openssl req -newkey rsa:2048 -sha256 -nodes -subj "/CN=$cn" -keyout "/tmp/pilot-tls/$peer.key" -out "/tmp/pilot-tls/$peer.csr" >/dev/null 2>&1
  openssl x509 -req -in "/tmp/pilot-tls/$peer.csr" -CA /tmp/pilot-tls/ca.crt -CAkey /tmp/pilot-tls/ca.key -CAcreateserial -days 1 -sha256 -out "/tmp/pilot-tls/$peer.crt" >/dev/null 2>&1
done
chown -R postgres:postgres /tmp/pilot-tls
chmod 600 /tmp/pilot-tls/*.key
printf 'local all all trust\nhostssl all all 127.0.0.1/32 cert\n' > /tmp/pgdata/pg_hba.conf
chown postgres:postgres /tmp/pgdata/pg_hba.conf
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/pgdata -o '-k /tmp/pgsocket -p 55431 -h 127.0.0.1 -c shared_preload_libraries=pg_stat_statements -c wal_level=logical -c ssl=on -c ssl_cert_file=/tmp/pilot-tls/server.crt -c ssl_key_file=/tmp/pilot-tls/server.key -c ssl_ca_file=/tmp/pilot-tls/ca.crt' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/pgdata -m immediate stop >/dev/null 2>&1 || true' EXIT
psql=(runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/pgsocket -p 55431 -d postgres)
"${psql[@]}" -Atqc 'SELECT version()' | grep -F "PostgreSQL $pg_version"
"${psql[@]}" -f /tests/schema.sql
"${psql[@]}" -f /tests/builtins/basic.sql
"${psql[@]}" -v loopback_conninfo='host=/tmp/pgsocket port=55431 dbname=postgres' -v loopback_host=/tmp/pgsocket -v loopback_port=55431 -f /tests/builtins/loopback.sql
"${psql[@]}" -v fixture_path=/tests/builtins/file_fdw.csv -f /tests/builtins/fixture.sql
"${psql[@]}" -f /tests/builtins/preloaded.sql
"${psql[@]}" -f /tests/builtins/wal.sql
tcn_output=$("${psql[@]}" -f /tests/builtins/tcn.sql)
printf '%s\n' "$tcn_output"
grep -F "Asynchronous notification \"tcn\" with payload \"\"builtin_tcn\",I,\"id\"='91'\"" <<< "$tcn_output"
runuser -u postgres -- env PGSSLMODE=verify-ca PGSSLROOTCERT=/tmp/pilot-tls/ca.crt PGSSLCERT=/tmp/pilot-tls/client.crt PGSSLKEY=/tmp/pilot-tls/client.key "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55431 -d postgres -f /tests/builtins/ssl.sql
if [[ $pg_version == 18.* ]]; then
  "${psql[@]}" -f /tests/builtins/logical.sql
fi
if [[ $pg_version == 15.* || $pg_version == 16.* ]]; then
  "${psql[@]}" -f /tests/builtins/legacy.sql
fi
"${psql[@]}" <<'SQL'
CREATE COLLATION pilot_icu (provider = icu, locale = 'en-US-u-kn-true', deterministic = false);
CREATE COLLATION pilot_libc (provider = libc, locale = 'C');
SELECT 'a' < 'b' COLLATE pilot_icu;
SELECT 'a' < 'b' COLLATE pilot_libc;
CREATE TABLE compression_probe (id integer, lz text COMPRESSION lz4, native text COMPRESSION pglz);
INSERT INTO compression_probe VALUES (1, repeat('compress me', 1000), repeat('compress me', 1000));
DO $$ BEGIN IF (SELECT pg_column_compression(lz) FROM compression_probe) <> 'lz4' THEN
  RAISE EXCEPTION 'LZ4 compression not used'; END IF; END $$;
SET wal_compression = zstd;
SHOW wal_compression;
SQL
"${psql[@]}" -f /tests/extensions/pgvector.sql
"${psql[@]}" -f /tests/builtins/coverage.sql
if [[ $pg_version == 15.* ]]; then
  dump_compression=(-Z 1)
else
  dump_compression=(-Z zstd:1)
fi
runuser -u postgres -- "$pgroot/bin/pg_dump" -h /tmp/pgsocket -p 55431 -Fc "${dump_compression[@]}" -f /tmp/probe.dump postgres
"${psql[@]}" -c 'CREATE DATABASE restored'
runuser -u postgres -- "$pgroot/bin/pg_restore" --exit-on-error -h /tmp/pgsocket -p 55431 -d restored /tmp/probe.dump
restored=(runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/pgsocket -p 55431 -d restored)
"${restored[@]}" <<'SQL'
DO $$ BEGIN
  IF pilot.active_item_count(1) <> 1 THEN RAISE EXCEPTION 'restored function or data missing'; END IF;
  IF (SELECT count(*) FROM pilot.events_2026) <> 1 THEN RAISE EXCEPTION 'restored partition data missing'; END IF;
  IF (SELECT extversion FROM pg_extension WHERE extname = 'vector') <> '0.8.7' THEN
    RAISE EXCEPTION 'restored pgvector missing'; END IF;
  IF (SELECT embedding <-> '[1,0,0]'::vector FROM pilot_vectors WHERE id = 1) <> 0 THEN
    RAISE EXCEPTION 'restored vector data missing'; END IF;
END $$;
SQL
"${psql[@]}" -c 'CREATE DATABASE surgery_check'
surgery=(runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/pgsocket -p 55431 -d surgery_check)
"${surgery[@]}" -f /tests/builtins/surgery.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/pgdata -m fast -w stop
trap - EXIT
. /etc/os-release
echo "PASS: moved PostgreSQL $pg_version archive and pgvector 0.8.7 archive on $PRETTY_NAME"
