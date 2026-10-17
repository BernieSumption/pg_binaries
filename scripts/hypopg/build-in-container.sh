#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
pg_version=${PG_VERSION:-18.6}
hypopg_version=1.4.3
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
hypopg_archive="hypopg-${hypopg_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
mkdir -p /work/prefix /work/source /work/stage /out
tar -xzf "$pg_archive" -C /work/prefix
mv /work/prefix/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
export PATH="$pgroot/bin:$PATH"
cd /work/source
curl -fL --retry 3 -o hypopg.tar.gz 'https://github.com/HypoPG/hypopg/archive/refs/tags/1.4.3.tar.gz'
echo '498a961d88cf37057fd9e98027d06fe805c8959d51895c3d9b94c9eb4e14f706  hypopg.tar.gz' | sha256sum -c -
tar -xzf hypopg.tar.gz
cd "hypopg-${hypopg_version}"
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" hypopg.control)" = "$hypopg_version"
make -j 4
make install DESTDIR=/work/stage
install_root=/work/stage/opt/postgresql
mkdir -p /work/package/hypopg/{lib,share/extension,LICENSES}
cp "$install_root/lib/hypopg.so" /work/package/hypopg/lib/
cp "$install_root/share/extension/"* /work/package/hypopg/share/extension/
cp LICENSE /work/package/hypopg/LICENSES/HypoPG.txt
cat > /work/package/metadata.json <<EOF
{"project":"hypopg","version":"${hypopg_version}","sql_names":["hypopg"],"requires":[],"configuration_prerequisites":[],"runtime_prerequisites":[],"postgresql_version":"${pg_version}","platform":"linux","architecture":"${architecture}","source":{"url":"https://github.com/HypoPG/hypopg/archive/refs/tags/1.4.3.tar.gz","sha256":"498a961d88cf37057fd9e98027d06fe805c8959d51895c3d9b94c9eb4e14f706"}}
EOF
cp /work/package/hypopg/lib/hypopg.so "$pgroot/lib/"
cp /work/package/hypopg/share/extension/* "$pgroot/share/extension/"
useradd -m postgres
mkdir -p /work/data /work/socket
chown postgres:postgres /work/data /work/socket
runuser -u postgres -- "$pgroot/bin/initdb" -D /work/data --encoding=UTF8 --locale=C --no-instructions
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -o '-k /work/socket -p 55432 -h ""' -w start
trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m immediate stop >/dev/null 2>&1 || true' EXIT
runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h /work/socket -p 55432 -d postgres -f /work/probe.sql | tee /work/probe.out
grep -Eq 'Index Scan using .*btree_hypo_probe_id' /work/probe.out
runuser -u postgres -- "$pgroot/bin/pg_ctl" -D /work/data -m fast -w stop
trap - EXIT
cd /work/package
tar -czf "/out/$hypopg_archive" hypopg metadata.json
cd /out
sha256sum "$hypopg_archive" > "$hypopg_archive.sha256"
