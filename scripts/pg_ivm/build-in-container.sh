#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
if [[ ! $pg_version =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Unsupported PostgreSQL version: $pg_version" >&2; exit 2
fi
version=1.16
source_url='https://github.com/sraoss/pg_ivm/archive/refs/tags/v1.16.tar.gz'
source_sha256='87807d6af1974fce591715d55f75d939dffea33ea6908b413e62d3dd79b9c583'
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
archive="pg_ivm-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
mkdir -p /work/prefix /work/source /work/stage /out
tar -xzf "$pg_archive" -C /work/prefix
mv /work/prefix/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
export PATH="$pgroot/bin:$PATH"
cd /work/source
curl -fL --retry 3 -o pg_ivm.tar.gz "$source_url"
printf '%s  %s\n' "$source_sha256" pg_ivm.tar.gz | sha256sum -c -
tar -xzf pg_ivm.tar.gz
cd pg_ivm-1.16
test "$(sed -n "s/^default_version = '\\([^']*\\)'/\\1/p" pg_ivm.control)" = "$version"
test "$(sed -n "s/^schema = \\([^ ]*\\)/\\1/p" pg_ivm.control)" = pg_catalog
make PG_CONFIG="$pgroot/bin/pg_config" -j 4
make PG_CONFIG="$pgroot/bin/pg_config" install DESTDIR=/work/stage
install_root=/work/stage/opt/postgresql
mkdir -p /work/package/pg_ivm/{lib,share/extension,bin,LICENSES}
cp "$install_root/lib/pg_ivm.so" /work/package/pg_ivm/lib/
cp "$install_root/share/extension/"* /work/package/pg_ivm/share/extension/
cp "$install_root/bin/pg_ivm_dump_metadata" /work/package/pg_ivm/bin/
cp LICENSE /work/package/pg_ivm/LICENSES/pg_ivm.txt
cat > /work/package/pg_ivm/LICENSES/pg_ivm-inventory.json <<EOL
{"schema_version":1,"components":[{"component":"pg_ivm","version":"${version}","payload_paths":["lib/pg_ivm.so","share/extension","bin/pg_ivm_dump_metadata"],"license_file":"pg_ivm.txt","license_source":"https://github.com/sraoss/pg_ivm/blob/v1.16/LICENSE","source_url":"${source_url}","source_sha256":"${source_sha256}","redistribution_review":{"status":"resolved","basis":"The unmodified pg_ivm 1.16 source includes its full PostgreSQL-style licence notice, which permits binary redistribution when the notice, permission and disclaimer paragraphs are retained.","source_obligation":"none"}}]}
EOL
cat > /work/package/metadata.json <<EOL
{"project":"pg_ivm","version":"${version}","sql_names":["pg_ivm"],"requires":[],"configuration_prerequisites":[{"type":"postgresql_setting","name":"shared_preload_libraries","value":"pg_ivm"}],"runtime_prerequisites":[],"postgresql_version":"${pg_version}","platform":"linux","architecture":"${architecture}","source":{"url":"${source_url}","sha256":"${source_sha256}"}}
EOL
cp /work/package/pg_ivm/lib/pg_ivm.so "$pgroot/lib/"
cp /work/package/pg_ivm/share/extension/* "$pgroot/share/extension/"
useradd -m postgres
mkdir -p /work/data /work/socket
chown postgres:postgres /work/data /work/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /work/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -l /work/data/server.log -o "-k /work/socket -p 55432 -h '' -c shared_preload_libraries=pg_ivm" -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /work/socket -p 55432 -d postgres -f /work/probe.sql
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m fast -w stop
trap - EXIT
cd /work/package
tar -czf "/out/$archive" pg_ivm metadata.json
cd /out
sha256sum "$archive" > "$archive.sha256"
