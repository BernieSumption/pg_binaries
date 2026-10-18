#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
extension_version=2.4.0
extension_sql_version=2.4
source_commit=2de2db763db9f590cd28159741c36b41f66eb985
source_sha256=21e4fe737e8eeb5a5ae96df781c61e3ceb74d481041a136e42503be636dc9fe8
source_url="https://github.com/percona/pg_stat_monitor/archive/refs/tags/${extension_version}.tar.gz"
[[ $pg_version == 18.6 && $architecture == x86_64 ]] || { echo 'Unsupported build target' >&2; exit 2; }
[[ $(uname -m) == x86_64 ]]
core_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
archive="pg_stat_monitor-${extension_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "${core_archive}.sha256"
mkdir -p /work/core /work/source /work/stage /work/package
tar -xzf "$core_archive" -C /work/core
pgroot=/work/core/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"

cd /work/source
curl -fL --retry 3 -o pg_stat_monitor-source.tar.gz "$source_url"
printf '%s  %s\n' "$source_sha256" pg_stat_monitor-source.tar.gz | sha256sum -c -
tar -xzf pg_stat_monitor-source.tar.gz
cd "pg_stat_monitor-${extension_version}"
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" pg_stat_monitor.control)" = "$extension_sql_version"

pkglibdir=$("$pgroot/bin/pg_config" --pkglibdir)
sharedir=$("$pgroot/bin/pg_config" --sharedir)
make -s PG_CONFIG="$pgroot/bin/pg_config" -j"$(nproc)"
make -s PG_CONFIG="$pgroot/bin/pg_config" DESTDIR=/work/stage install

package=/work/package/pg_stat_monitor
mkdir -p "$package/lib" "$package/share/extension" "$package/LICENSES/pg_stat_monitor"
cp "/work/stage$pkglibdir/pg_stat_monitor.so" "$package/lib/"
cp /work/stage"$sharedir"/extension/pg_stat_monitor* "$package/share/extension/"
test -s "$package/lib/pg_stat_monitor.so"
test -s "$package/share/extension/pg_stat_monitor.control"
cp LICENSE "$package/LICENSES/pg_stat_monitor/LICENSE"
cat > /work/package/metadata.json <<EOF
{
  "project": "pg_stat_monitor",
  "version": "${extension_version}",
  "sql_names": ["pg_stat_monitor"],
  "requires": [],
  "configuration_prerequisites": [{"type": "postgresql_setting", "name": "shared_preload_libraries", "value": "pg_stat_monitor"}],
  "runtime_prerequisites": [],
  "postgresql_version": "${pg_version}",
  "platform": "linux",
  "architecture": "${architecture}",
  "release_eligible": false,
  "source_archive": {"url": "${source_url}", "sha256": "${source_sha256}", "commit": "${source_commit}"}
}
EOF
mkdir -p /out/static-analysis
tar -C /work/package -czf "/out/${archive}" pg_stat_monitor metadata.json
cd /out
sha256sum "$archive" > "${archive%.tar.gz}.sha256"
printf 'source_url=%s\nsource_commit=%s\nsource_archive_sha256=%s\n' \
  "$source_url" "$source_commit" "$source_sha256" > build-evidence.txt
printf 'postgresql_version=%s\narchitecture=%s\n' "$pg_version" "$architecture" >> build-evidence.txt
