#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
test "$architecture" = x86_64 && test "$(uname -m)" = x86_64
extension_version=5.5.0
source_url="https://api.pgxn.org/dist/pg_partman/${extension_version}/pg_partman-${extension_version}.zip"
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
mkdir -p /work/core /work/source /work/stage /out
tar -xzf "$pg_archive" -C /work/core
mv /work/core/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
curl --proto '=https' --tlsv1.2 -fsSLo /work/pg_partman.zip "$source_url"
unzip -q /work/pg_partman.zip -d /work/source
src=/work/source/pg_partman-${extension_version}
test -f "$src/META.json" && test -f "$src/LICENSE.txt" && test -f "$src/pg_partman.control"
test "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$src/META.json")" = "$extension_version"
make -C "$src" PG_CONFIG="$pgroot/bin/pg_config"
make -C "$src" PG_CONFIG="$pgroot/bin/pg_config" DESTDIR=/work/stage install
package=/work/package/pg_partman
mkdir -p "$package/lib" "$package/share/extension" "$package/LICENSES/pg_partman"
sharedir=$("$pgroot/bin/pg_config" --sharedir)
pkglibdir=$("$pgroot/bin/pg_config" --pkglibdir)
install -m 755 "/work/stage$pkglibdir/pg_partman_bgw.so" "$package/lib/pg_partman_bgw.so"
install -m 644 /work/stage"$sharedir"/extension/pg_partman* "$package/share/extension/"
install -m 644 "$src/LICENSE.txt" "$package/LICENSES/pg_partman/LICENSE.txt"
python3 - "$extension_version" "$pg_version" "$architecture" "$source_url" /work/pg_partman.zip <<'PY'
import hashlib, json, pathlib, sys
version, pg, arch, url, source = sys.argv[1:]
digest = hashlib.sha256(pathlib.Path(source).read_bytes()).hexdigest()
metadata = {
    'project': 'pg_partman', 'version': version, 'sql_names': ['pg_partman'],
    'requires': [], 'configuration_prerequisites': [], 'runtime_prerequisites': [],
    'postgresql_version': pg, 'platform': 'linux', 'architecture': arch,
    'source_archive': {'url': url, 'sha256': digest}, 'release_eligible': False,
}
pathlib.Path('/work/package/metadata.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
PY
tar -C /work/package -czf "/out/pg_partman-${extension_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz" pg_partman metadata.json
cd /out
sha256sum pg_partman-*.tar.gz > pg_partman.sha256
