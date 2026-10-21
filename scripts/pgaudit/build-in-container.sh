#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
case "$pg_version" in
  15.19)
    version=1.7.1
    source_ref=72da89c3fa02f3f2b9f3933214d91ad9c3428467
    source_url="https://api.github.com/repos/pgaudit/pgaudit/tarball/$source_ref"
    source_sha256=1e52448238908a09e0e78b3375dcefbfca51509fdbb3a4d92eb710e380ed3567
    ;;
  16.15)
    version=16.1
    source_ref=a81792e8a4ea8f7aaf75bd610fcc4c2f96650bdc
    source_url="https://api.github.com/repos/pgaudit/pgaudit/tarball/$source_ref"
    source_sha256=b0648fcebe5a67340c406126e6dddc703fd03821a9ace80390e128a0d1c91c73
    ;;
  17.11)
    version=17.1
    source_ref=538f89a93d8fd0d8913f3d740cacaea7b7eb66d9
    source_url="https://api.github.com/repos/pgaudit/pgaudit/tarball/$source_ref"
    source_sha256=20e980bd0c22b4ae33305ec2b774bd846bf343642adad108b6c28b422a648312
    ;;
  18.6)
    version=18.0
    source_ref=18.0
    source_url='https://github.com/pgaudit/pgaudit/archive/refs/tags/18.0.tar.gz'
    source_sha256=988e8afeda320ebe0a3e632ef6b6bce5d3a08346c2e100a173a585c9521d1fa5
    ;;
  *) echo "Unsupported PostgreSQL version for pgAudit: $pg_version" >&2; exit 2 ;;
esac
if [[ "$pg_version" == 18.6 ]]; then
  source_root=pgaudit-18.0
else
  source_root="pgaudit-pgaudit-${source_ref:0:7}"
fi
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
test "$(tar -tzf pgaudit.tar.gz | cut -d/ -f1 | sort -u)" = "$source_root"
tar -xzf pgaudit.tar.gz
test -f "/work/source/$source_root/pgaudit.control"
cd "/work/source/$source_root"
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" pgaudit.control)" = "$version"
make USE_PGXS=1 -j 4
make USE_PGXS=1 install DESTDIR=/work/stage
install_root=/work/stage/opt/postgresql
mkdir -p /work/package/pgaudit/{lib,share/extension}
cp "$install_root/lib/pgaudit.so" /work/package/pgaudit/lib/
cp "$install_root/share/extension/"* /work/package/pgaudit/share/extension/
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
python3 /usr/local/bin/license_pointer.py write /work/package/pgaudit pgaudit
tar -czf "/out/$archive" pgaudit metadata.json
cd /out
sha256sum "$archive" > "$archive.sha256"
