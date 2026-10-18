#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
extension_version=2.4.0
source_tag=2.4.0
source_url="https://github.com/percona/pg_stat_monitor/archive/refs/tags/${source_tag}.tar.gz"
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
git init -q pg_stat_monitor
git -C pg_stat_monitor remote add origin https://github.com/percona/pg_stat_monitor.git
git -C pg_stat_monitor fetch --depth 1 origin "refs/tags/${source_tag}"
git -C pg_stat_monitor checkout --detach FETCH_HEAD
source_commit=$(git -C pg_stat_monitor rev-parse HEAD)
test "$(git -C pg_stat_monitor describe --tags --exact-match HEAD)" = "$source_tag"
cd pg_stat_monitor
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" pg_stat_monitor.control)" = "$extension_version"

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
source_sha256=$(git archive --format=tar HEAD | sha256sum | cut -d' ' -f1)
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
