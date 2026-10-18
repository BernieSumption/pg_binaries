#!/usr/bin/env bash
set -euo pipefail
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
test "$architecture" = x86_64 && test "$(uname -m)" = x86_64
extension_version=1.5.3
source_url="https://api.pgxn.org/dist/pg_repack/pg_repack-${extension_version}.zip"
pg_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$pg_archive.sha256"
mkdir -p /work/core /work/source /work/stage /out
tar -xzf "$pg_archive" -C /work/core
mv /work/core/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
curl --proto '=https' --tlsv1.2 -fsSLo /work/pg_repack.zip "$source_url"
unzip -q /work/pg_repack.zip -d /work/source
src=/work/source/pg_repack-${extension_version}
test -f "$src/META.json" && test -f "$src/COPYRIGHT"
test "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$src/META.json")" = "$extension_version"
make -C "$src" PG_CONFIG="$pgroot/bin/pg_config" USE_PGXS=1
make -C "$src" PG_CONFIG="$pgroot/bin/pg_config" USE_PGXS=1 DESTDIR=/work/stage install
package=/work/package/pg_repack
mkdir -p "$package/lib" "$package/bin" "$package/libexec" "$package/share/extension" "$package/LICENSES/pg_repack"
sharedir=$("$pgroot/bin/pg_config" --sharedir)
pkglibdir=$("$pgroot/bin/pg_config" --pkglibdir)
bindir=$("$pgroot/bin/pg_config" --bindir)
install -m 755 "/work/stage$pkglibdir/pg_repack.so" "$package/lib/pg_repack.so"
install -m 755 "/work/stage$bindir/pg_repack" "$package/libexec/pg_repack"
patchelf --set-rpath '$ORIGIN/../lib:$ORIGIN/../lib/runtime' "$package/libexec/pg_repack"
install -m 755 "$pgroot/bin/.pg-launcher" "$package/bin/pg_repack"
install -m 644 /work/stage"$sharedir"/extension/pg_repack* "$package/share/extension/"
install -m 644 "$src/COPYRIGHT" "$package/LICENSES/pg_repack/COPYRIGHT"
python3 - "$extension_version" "$pg_version" "$architecture" "$source_url" /work/pg_repack.zip <<'PY'
import hashlib, json, pathlib, sys
version, pg, arch, url, source = sys.argv[1:]
digest = hashlib.sha256(pathlib.Path(source).read_bytes()).hexdigest()
meta = {
    'project': 'pg_repack', 'version': version, 'sql_names': ['pg_repack'],
    'requires': [], 'configuration_prerequisites': [], 'runtime_prerequisites': [],
    'postgresql_version': pg, 'platform': 'linux', 'architecture': arch,
    'source_archive': {'url': url, 'sha256': digest},
    'release_eligible': False,
}
pathlib.Path('/work/package/metadata.json').write_text(json.dumps(meta, indent=2, sort_keys=True) + '\n')
PY
tar -C /work/package -czf "/out/pg_repack-${extension_version}-postgresql-${pg_version}-linux-${architecture}.tar.gz" pg_repack metadata.json
cd /out
sha256sum pg_repack-*.tar.gz > pg_repack.sha256
