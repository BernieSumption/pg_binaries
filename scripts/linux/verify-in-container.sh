#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
vector_version=${PGVECTOR_VERSION:-0.8.7}
verify_mode=${PG_VERIFY_MODE:-full}
case "$verify_mode" in full|core-only) ;; *) echo "Unsupported Linux verification mode: $verify_mode (expected full or core-only)" >&2; exit 2 ;; esac
if [[ $verify_mode == full ]]; then
  [[ $vector_version =~ ^[0-9]+(\.[0-9]+)+$ ]] || { echo "Invalid pgvector release: $vector_version" >&2; exit 2; }
fi
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
vector="pgvector-${vector_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /out
sha256sum -c "$pg.sha256"
if [[ $verify_mode == full ]]; then sha256sum -c "$vector.sha256"; fi
python3 /usr/local/bin/license_pointer.py verify "/out/$pg" postgresql
if [[ $verify_mode == full ]]; then
  python3 /usr/local/bin/license_pointer.py verify "/out/$vector" pgvector
fi
useradd -m postgres
install -d -o postgres -g postgres /tmp/first /tmp/moved /tmp/vector
runuser -u postgres -- tar -xzf "$pg" -C /tmp/first
if [[ $verify_mode == full ]]; then runuser -u postgres -- tar -xzf "$vector" -C /tmp/vector; fi
python3 - "$pg_version" "$architecture" "$vector_version" "$verify_mode" <<'PY'
import hashlib
import json
from pathlib import Path
import re
import sys
version = sys.argv[1]
architecture = sys.argv[2]
vector_version = sys.argv[3]
verify_mode = sys.argv[4]
with open('/tmp/first/postgresql/manifest.json') as f:
    m = json.load(f)
assert (m['schema_version'], m['component'], m['version'],
        m['postgresql_version'], m['platform'], m['architecture']) == (
            1, 'postgresql', version, version, 'linux', architecture), m
provenance_fields = ('build_id', 'source_revision', 'build_configuration', 'builder_image_id', 'platform', 'architecture')
provenance = {field: m[field] for field in provenance_fields}
assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', provenance['build_id']), provenance
assert re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', provenance['source_revision']), provenance
assert re.fullmatch(r'sha256:[0-9a-f]{64}', provenance['builder_image_id']), provenance
assert provenance['build_configuration'] and provenance['platform'] == 'linux' and provenance['architecture'] == architecture, provenance
controls = {path.stem for path in Path('/tmp/first/postgresql/share/extension').glob('*.control')}
assert controls and m['included_extensions'] == sorted(controls), m
assert 'vector' not in controls, controls

root = Path('/tmp/first/postgresql')
wrappers = {path.name for path in (root / 'bin').iterdir()
            if path.is_file() and not path.is_symlink() and path.name != '.pg-launcher'}
payloads = {path.name for path in (root / 'libexec').iterdir()}
assert wrappers == payloads, (wrappers, payloads)
launcher = root / 'bin/.pg-launcher'
assert launcher.read_bytes().startswith(b'\x7fELF'), launcher
assert all((root / 'bin' / name).stat().st_ino == launcher.stat().st_ino for name in wrappers)

if verify_mode == 'full':
    with open('/tmp/vector/metadata.json') as f:
        m = json.load(f)
    expected_vector = {
        'project': 'pgvector', 'version': vector_version, 'sql_names': ['vector'],
        'requires': [], 'configuration_prerequisites': [], 'runtime_prerequisites': [],
    }
    assert all(m.get(key) == value for key, value in expected_vector.items()), m
    extension_provenance = {field: m[field] for field in provenance_fields}
    if 'core_archive' not in m:
        assert extension_provenance == provenance, m
    else:
        core_archive = Path('/out') / f'postgresql-{version}-linux-{architecture}.tar.gz'
        digest = hashlib.sha256()
        with core_archive.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        assert m['core_archive'] == {'basename': core_archive.name, 'sha256': digest.hexdigest()}, m
        assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', extension_provenance['build_id']), m
        assert re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', extension_provenance['source_revision']), m
        assert re.fullmatch(r'sha256:[0-9a-f]{64}', extension_provenance['builder_image_id']), m
        assert isinstance(extension_provenance['build_configuration'], str) and extension_provenance['build_configuration'], m
        assert (extension_provenance['platform'], extension_provenance['architecture']) == ('linux', architecture), m
PY
if [[ $verify_mode == full ]]; then
  python3 /verification/tools/check_source_identity.py --root /verification --platform linux \
    --postgresql-version "$pg_version" --pgvector-version "$vector_version" \
    --core-manifest /tmp/first/postgresql/manifest.json --vector-metadata /tmp/vector/metadata.json
else
  python3 - "$pg_version" /tmp/first/postgresql/manifest.json <<'PYCORE'
import json, sys
from pathlib import Path
sys.path.insert(0, '/verification/tools')
from source_archive import source_archive
manifest = json.loads(Path(sys.argv[2]).read_text())
assert manifest.get('source_archive') == source_archive('postgresql', sys.argv[1], 'tar.bz2', Path('/verification'))
PYCORE
fi
pgroot=/tmp/first/postgresql
if [[ $verify_mode == full ]]; then
  python3 /usr/local/bin/linux-assembly-inventory \
    --core-archive "/out/$pg" --extension-archive "/out/$vector" \
    --postgresql-version "$pg_version" --extension-version "$vector_version" \
    --platform "linux-$architecture" --output /tmp/assembly-inventory.json
  runuser -u postgres -- python3 /usr/local/bin/stage-extension-archive \
    --inventory /tmp/assembly-inventory.json --support /verification/support.json \
    --postgresql-version "$pg_version" --platform "linux-$architecture" \
    --project pgvector --extension-version "$vector_version" --sql-name vector \
    --archive-directory /out --prefix "$pgroot" --staging-root /tmp/extension-staging
  python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" \
    --archive "/out/$pg" --archive "/out/$vector" --report /analysis/core-pgvector.json
else
  python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" \
    --archive "/out/$pg" --report /analysis/core.json
fi
test "$(/tmp/first/postgresql/bin/postgres --version)" = "postgres (PostgreSQL) $pg_version"
if [[ $verify_mode == full ]]; then
mkdir -p /tmp/first-data /tmp/first-socket
chown postgres:postgres /tmp/first-data /tmp/first-socket
runuser -u postgres -- /tmp/first/postgresql/bin/initdb -D /tmp/first-data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- /tmp/first/postgresql/bin/pg_ctl -D /tmp/first-data -o '-k /tmp/first-socket -p 55430 -h ""' -w start
trap 'runuser -u postgres -- /tmp/first/postgresql/bin/pg_ctl -D /tmp/first-data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- /tmp/first/postgresql/bin/psql -XAt -h /tmp/first-socket -p 55430 -d postgres -c 'SHOW server_version' | grep -Fx "$pg_version"
runuser -u postgres -- /tmp/first/postgresql/bin/psql -XAt -v ON_ERROR_STOP=1 -h /tmp/first-socket -p 55430 -d postgres -c 'SELECT datcollate FROM pg_database WHERE datname = current_database()' | grep -Fx C
runuser -u postgres -- /tmp/first/postgresql/bin/psql -X -v ON_ERROR_STOP=1 -h /tmp/first-socket -p 55430 -d postgres <<'SQL'
CREATE EXTENSION vector;
CREATE TABLE relocation_probe (embedding vector(3));
INSERT INTO relocation_probe VALUES ('[1,0,0]');
DO $$ BEGIN IF (SELECT embedding <-> '[1,0,0]'::vector FROM relocation_probe) <> 0 THEN
  RAISE EXCEPTION 'pgvector smoke test failed'; END IF; END $$;
SQL
runuser -u postgres -- /tmp/first/postgresql/bin/pg_ctl -D /tmp/first-data -m fast -w stop
trap - EXIT
fi
runuser -u postgres -- mv /tmp/first/postgresql /tmp/moved/postgresql
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
if [[ $verify_mode == full ]]; then "${psql[@]}" -f /tests/extensions/pgvector.sql; fi
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
  IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'pilot') THEN
    RAISE EXCEPTION 'restored pilot schema missing'; END IF;
  IF pilot.active_item_count(1) <> 1 THEN RAISE EXCEPTION 'restored function or data missing'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'pilot' AND p.proname = 'active_item_count'
      AND p.prokind = 'f'
  ) THEN RAISE EXCEPTION 'restored function missing from catalogue'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_class r
    JOIN pg_namespace n ON n.oid = r.relnamespace
    WHERE n.nspname = 'pilot' AND r.relname = 'active_items' AND r.relkind = 'v'
  ) THEN RAISE EXCEPTION 'restored view missing from catalogue'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c
    JOIN pg_class r ON r.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = r.relnamespace
    WHERE n.nspname = 'pilot' AND r.relname = 'items'
      AND c.conname = 'items_title_check' AND c.contype = 'c'
  ) THEN RAISE EXCEPTION 'restored check constraint missing'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_class i
    JOIN pg_namespace n ON n.oid = i.relnamespace
    JOIN pg_index x ON x.indexrelid = i.oid
    WHERE n.nspname = 'pilot' AND i.relname = 'items_title_key_active_idx'
      AND x.indisvalid AND x.indpred IS NOT NULL
  ) THEN RAISE EXCEPTION 'restored partial index missing'; END IF;
  IF (SELECT count(*) FROM pilot.events_2026) <> 1 THEN RAISE EXCEPTION 'restored partition data missing'; END IF;
END $$;
SQL
if [[ $verify_mode == full ]]; then
  "${restored[@]}" <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    RAISE EXCEPTION 'restored pgvector missing'; END IF;
  IF (SELECT embedding <-> '[1,0,0]'::vector FROM pilot_vectors WHERE id = 1) <> 0 THEN
    RAISE EXCEPTION 'restored vector data missing'; END IF;
END $$;
SQL
test "$("${psql[@]}" -Atqc "SELECT extversion FROM pg_extension WHERE extname = 'vector'")" = "$vector_version"
fi
"${psql[@]}" -c 'CREATE DATABASE surgery_check'
surgery=(runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /tmp/pgsocket -p 55431 -d surgery_check)
"${surgery[@]}" -f /tests/builtins/surgery.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /tmp/pgdata -m fast -w stop
trap - EXIT
. /etc/os-release
if [[ $verify_mode == full ]]; then
  echo "PASS: moved PostgreSQL $pg_version archive and pgvector $vector_version archive on $PRETTY_NAME"
else
  echo "PASS: moved PostgreSQL $pg_version archive on $PRETTY_NAME (core-only mode; pgvector not checked)"
fi
