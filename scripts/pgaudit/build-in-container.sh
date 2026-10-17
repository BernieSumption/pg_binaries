#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=18.6
version=18.0
source_url='https://github.com/pgaudit/pgaudit/archive/refs/tags/18.0.tar.gz'
source_sha256='988e8afeda320ebe0a3e632ef6b6bce5d3a08346c2e100a173a585c9521d1fa5'
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
archive="pgaudit-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
mkdir -p /work/prefix /work/source /work/stage /out
tar -xzf "$pg_archive" -C /work/prefix
mv /work/prefix/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
export PATH="$pgroot/bin:$PATH"
cd /work/source
curl -fL --retry 3 -o pgaudit.tar.gz "$source_url"
echo "$source_sha256  pgaudit.tar.gz" | sha256sum -c -
tar -xzf pgaudit.tar.gz
cd pgaudit-18.0
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" pgaudit.control)" = "$version"
make USE_PGXS=1 -j 4
make USE_PGXS=1 install DESTDIR=/work/stage
install_root=/work/stage/opt/postgresql
mkdir -p /work/package/pgaudit/{lib,share/extension,LICENSES}
cp "$install_root/lib/pgaudit.so" /work/package/pgaudit/lib/
cp "$install_root/share/extension/"* /work/package/pgaudit/share/extension/
cat LICENSE "$pgroot/LICENSES/PostgreSQL.txt" > /work/package/pgaudit/LICENSES/pgAudit.txt
grep -Fq 'This code is released under the PostgreSQL licence' /work/package/pgaudit/LICENSES/pgAudit.txt
grep -Fq 'Permission to use, copy, modify, and distribute this software' /work/package/pgaudit/LICENSES/pgAudit.txt
cat > /work/package/pgaudit/LICENSES/inventory.json <<EOF
{
  "schema_version": 1,
  "components": [{
    "component": "pgaudit",
    "version": "${version}",
    "payload_paths": ["lib/pgaudit.so", "share/extension"],
    "license_file": "pgAudit.txt",
    "license_source": "https://github.com/pgaudit/pgaudit/tree/18.0/LICENSE",
    "source_url": "${source_url}",
    "source_sha256": "${source_sha256}",
    "redistribution_review": {
      "status": "resolved",
      "basis": "The unmodified pgAudit 18.0 LICENSE points to the PostgreSQL licence and names the PostgreSQL Global Development Group. This package retains that upstream notice with the full PostgreSQL licence text already included in the selected PostgreSQL 18.6 archive. The licence permits binary redistribution with the notice and terms retained and requires no source delivery.",
      "source_obligation": "none"
    }
  }]
}
EOF
cat > /work/package/metadata.json <<EOF
{"project":"pgaudit","version":"${version}","sql_names":["pgaudit"],"requires":[],"configuration_prerequisites":[{"type":"postgresql_setting","name":"shared_preload_libraries","value":"pgaudit"}],"runtime_prerequisites":[],"postgresql_version":"${pg_version}","platform":"linux","architecture":"${architecture}","source":{"url":"${source_url}","sha256":"${source_sha256}"}}
EOF

cp /work/package/pgaudit/lib/pgaudit.so "$pgroot/lib/"
cp /work/package/pgaudit/share/extension/* "$pgroot/share/extension/"
useradd -m postgres
mkdir -p /work/data /work/socket
chown postgres:postgres /work/data /work/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /work/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -l /work/data/server.log -o "-k /work/socket -p 55432 -h '' -c shared_preload_libraries=pgaudit -c logging_collector=on -c log_directory=log -c log_filename=pgaudit.log" -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /work/socket -p 55432 -d postgres -f /work/probe.sql
log_file=/work/data/log/pgaudit.log
test -s "$log_file"
grep -F 'AUDIT: SESSION' "$log_file"
grep -F 'DDL' "$log_file" | grep -F 'CREATE TABLE public.pgaudit_probe'
grep -F 'WRITE' "$log_file" | grep -F 'INSERT INTO public.pgaudit_probe'
grep -F 'READ' "$log_file" | grep -F 'SELECT payload FROM public.pgaudit_probe'
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m fast -w stop
trap - EXIT
cd /work/package
tar -czf "/out/$archive" pgaudit metadata.json
cd /out
sha256sum "$archive" > "$archive.sha256"
