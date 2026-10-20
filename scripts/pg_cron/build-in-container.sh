#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
case "$architecture:$(uname -m)" in x86_64:x86_64|arm64:aarch64) ;; *) echo "Build container architecture does not match $architecture: $(uname -m)" >&2; exit 2 ;; esac
version=1.6.8
source_url='https://github.com/citusdata/pg_cron/archive/refs/tags/v1.6.8.tar.gz'
source_sha256='c19ab9bb35406c60fb51ecda993737c083850abe424acb6c1030439d00a1f8e4'
pg_version=${PG_VERSION:-18.6}
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
archive="pg_cron-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
core_sha256=$(sha256sum "$pg_archive" | awk '{print $1}')
mkdir -p /work/prefix /work/source /work/stage /out
tar -xzf "$pg_archive" -C /work/prefix
mv /work/prefix/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
export PATH="$pgroot/bin:$PATH"
cd /work/source
curl -fL --retry 3 -o pg_cron.tar.gz "$source_url"
printf '%s  %s\n' "$source_sha256" pg_cron.tar.gz | sha256sum -c -
tar -xzf pg_cron.tar.gz
cd pg_cron-1.6.8
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" pg_cron.control)" = 1.6
make PG_CONFIG="$pgroot/bin/pg_config" -j 4
make PG_CONFIG="$pgroot/bin/pg_config" install DESTDIR=/work/stage
install_root=/work/stage/opt/postgresql
mkdir -p /work/package/pg_cron/{lib,share/extension,LICENSES}
cp "$install_root/lib/pg_cron.so" /work/package/pg_cron/lib/
cp "$install_root/share/extension/pg_cron"* /work/package/pg_cron/share/extension/
cp LICENSE /work/package/pg_cron/LICENSES/pg_cron.txt
cat > /work/package/pg_cron/LICENSES/pg_cron-inventory.json <<EOL
{"schema_version":1,"components":[{"component":"pg_cron","version":"${version}","payload_paths":["lib/pg_cron.so","share/extension"],"license_file":"pg_cron.txt","license_source":"https://github.com/citusdata/pg_cron/blob/v1.6.8/LICENSE","source_url":"${source_url}","source_sha256":"${source_sha256}","redistribution_review":{"status":"resolved","basis":"The unmodified pg_cron 1.6.8 source archive includes the PostgreSQL License for this project. It permits binary redistribution with its copyright notice, permission paragraph and disclaimer retained; this archive includes the complete upstream LICENSE text.","source_obligation":"none"}}]}
EOL
cat > /work/package/metadata.json <<EOL
{"project":"pg_cron","version":"${version}","sql_names":["pg_cron"],"requires":[],"configuration_prerequisites":[{"type":"postgresql_setting","name":"shared_preload_libraries","value":"pg_cron"},{"type":"postgresql_setting","name":"cron.use_background_workers","value":"on"}],"runtime_prerequisites":[],"postgresql_version":"${pg_version}","core_archive":{"basename":"${pg_archive}","sha256":"${core_sha256}"},"platform":"linux","architecture":"${architecture}","source":{"url":"${source_url}","sha256":"${source_sha256}"}}
EOL
cp /work/package/pg_cron/lib/pg_cron.so "$pgroot/lib/"
cp /work/package/pg_cron/share/extension/* "$pgroot/share/extension/"
useradd -m postgres
mkdir -p /work/data /work/socket
chown postgres:postgres /work/data /work/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /work/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -l /work/data/server.log -o "-k /work/socket -p 55432 -h '' -c shared_preload_libraries=pg_cron -c cron.use_background_workers=on -c max_worker_processes=20 -c cron.database_name=postgres" -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /work/socket -p 55432 -d postgres -c 'CREATE EXTENSION pg_cron;'
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m fast -w stop
trap - EXIT
cd /work/package
tar -czf "/out/$archive" pg_cron metadata.json
cd /out
sha256sum "$archive" > "$archive.sha256"
