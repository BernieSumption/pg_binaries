#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
test "$pg_version" = 18.6 && test "$architecture" = x86_64 && test "$(uname -m)" = x86_64
extension_version=1.9.4
source_commit=400c5f6ae9bc911073a6824e9a19f4d475fb7331
source_url=https://github.com/cybertec-postgresql/pg_squeeze.git
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
mkdir -p /work/core /work/source /work/stage /out
tar -xzf "$pg_archive" -C /work/core
mv /work/core/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
git init -q /work/source/pg_squeeze
git -C /work/source/pg_squeeze remote add origin "$source_url"
git -C /work/source/pg_squeeze fetch -q --depth 1 origin refs/tags/REL1_9_4
git -C /work/source/pg_squeeze checkout -q --detach FETCH_HEAD
src=/work/source/pg_squeeze
test "$(git -C "$src" rev-parse HEAD)" = "$source_commit"
test -f "$src/LICENSE" && test -f "$src/pg_squeeze.control"
make -C "$src" PG_CONFIG="$pgroot/bin/pg_config" USE_PGXS=1
make -C "$src" PG_CONFIG="$pgroot/bin/pg_config" USE_PGXS=1 DESTDIR=/work/stage install
package=/work/package/pg_squeeze
mkdir -p "$package/lib" "$package/share/extension" "$package/LICENSES/pg_squeeze"
sharedir=$("$pgroot/bin/pg_config" --sharedir)
pkglibdir=$("$pgroot/bin/pg_config" --pkglibdir)
install -m 755 "/work/stage$pkglibdir/pg_squeeze.so" "$package/lib/pg_squeeze.so"
install -m 644 /work/stage"$sharedir"/extension/pg_squeeze* "$package/share/extension/"
install -m 644 "$src/LICENSE" "$package/LICENSES/pg_squeeze/LICENSE"
python3 - "$extension_version" "$pg_version" "$architecture" "$source_url" "$source_commit" <<'PY'
import json, pathlib, sys
version, pg, arch, url, commit = sys.argv[1:]
meta = {
    'project': 'pg_squeeze', 'version': version, 'sql_names': ['pg_squeeze'],
    'requires': [],
    'configuration_prerequisites': ['shared_preload_libraries=pg_squeeze', 'wal_level=logical'],
    'runtime_prerequisites': [], 'postgresql_version': pg,
    'platform': 'linux', 'architecture': arch,
    'source': {'repository': url, 'commit': commit},
    'release_eligible': False,
}
pathlib.Path('/work/package/metadata.json').write_text(json.dumps(meta, indent=2, sort_keys=True) + '\n')
PY
tar -C /work/package -czf "/out/pg_squeeze-${extension_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz" pg_squeeze metadata.json
cd /out
sha256sum pg_squeeze-*.tar.gz > pg_squeeze.sha256
