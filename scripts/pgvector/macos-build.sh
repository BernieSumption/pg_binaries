#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core_archive=${1:?usage: macos-build.sh CORE_ARCHIVE SOURCE_ARCHIVE OUTPUT_DIR PG_VERSION PGVECTOR_VERSION ARCHITECTURE}
source_archive=${2:?usage: macos-build.sh CORE_ARCHIVE SOURCE_ARCHIVE OUTPUT_DIR PG_VERSION PGVECTOR_VERSION ARCHITECTURE}
output=${3:?usage: macos-build.sh CORE_ARCHIVE SOURCE_ARCHIVE OUTPUT_DIR PG_VERSION PGVECTOR_VERSION ARCHITECTURE}
pg_version=${4:?}
vector_version=${5:?}
architecture=${6:?}
core_dsyms=${7:?usage: macos-build.sh CORE_ARCHIVE SOURCE_ARCHIVE OUTPUT_DIR PG_VERSION PGVECTOR_VERSION ARCHITECTURE CORE_DSYMS_DIR}
[[ "$vector_version" == 0.8.7 ]] || { echo "Unsupported macOS pgvector release: $vector_version" >&2; exit 2; }
case "$architecture" in arm64|x86_64) ;; *) echo "Unsupported macOS architecture: $architecture" >&2; exit 2 ;; esac
[[ $(uname -s) == Darwin && $(uname -m) == "$architecture" ]] || { echo "Build requires native macOS $architecture" >&2; exit 1; }

core_archive=$(cd "$(dirname "$core_archive")" && pwd)/$(basename "$core_archive")
source_archive=$(cd "$(dirname "$source_archive")" && pwd)/$(basename "$source_archive")
core_dsyms=$(cd "$core_dsyms" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/pgvector-macos.XXXXXX")
prefix_link=
cleanup() { [[ -z "$prefix_link" ]] || rm -f "$prefix_link"; rm -rf "$work"; }
trap cleanup EXIT

source_sha=$(python3 "$repo/tools/source_archive.py" pgvector "$vector_version" tar.gz --field sha256)
source_url=$(python3 "$repo/tools/source_archive.py" pgvector "$vector_version" tar.gz --field url)
core_source_sha=$(python3 "$repo/tools/source_archive.py" postgresql "$pg_version" tar.bz2 --field sha256)
python3 "$repo/scripts/pgvector/archive_input.py" validate-source "$source_archive" "$source_sha" "$vector_version"
python3 - "$core_archive" "$pg_version" "$architecture" "$core_source_sha" <<'PY'
import hashlib, json, pathlib, re, sys, tarfile
path = pathlib.Path(sys.argv[1])
version, arch, source_sha = sys.argv[2:]
sidecar = pathlib.Path(str(path) + '.sha256').read_text().split()
actual = hashlib.sha256(path.read_bytes()).hexdigest()
if len(sidecar) < 2 or sidecar[0] != actual or sidecar[-1] != path.name:
    raise SystemExit('core archive checksum sidecar does not match archive bytes')
if path.name != f'postgresql-{version}-macos-{arch}.tar.gz':
    raise SystemExit('core archive basename does not match selected macOS target')
with tarfile.open(path, 'r:gz') as archive:
    manifest = json.load(archive.extractfile('postgresql/manifest.json'))
if (manifest.get('component'), manifest.get('version'), manifest.get('platform'), manifest.get('architecture')) != ('postgresql', version, 'macos', arch):
    raise SystemExit('core manifest identity does not match selected macOS target')
if manifest.get('source_archive', {}).get('sha256') != source_sha:
    raise SystemExit('core archive source identity differs from selected PostgreSQL release')
PY

tar -xzf "$core_archive" -C "$work"
pgroot="$work/postgresql"
python3 - "$pgroot/manifest.json" "$pg_version" "$architecture" > "$work/core-provenance.tsv" <<'PY'
import json, pathlib, re, sys
m = json.loads(pathlib.Path(sys.argv[1]).read_text())
if (m.get('version'), m.get('architecture'), m.get('platform')) != (sys.argv[2], sys.argv[3], 'macos'):
    raise SystemExit('resolved core manifest does not match the requested target')
build_id, revision = m.get('build_id'), m.get('source_revision')
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', build_id or '') or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', revision or ''):
    raise SystemExit('resolved core manifest has invalid build provenance')
h = pathlib.Path(sys.argv[1]).parent / 'include/server/pg_config.h'
text = h.read_text()
match = re.search(r'#define CONFIGURE_ARGS "[^\n]*?--prefix=([^\']+)', text)
if not match: raise SystemExit('cannot read original PostgreSQL installation prefix')
prefix = pathlib.Path(match.group(1))
if not re.fullmatch(r'/Users/runner/work/_temp/pg-macos-pilot\.[A-Za-z0-9]+/install/postgresql', str(prefix)):
    raise SystemExit(f'unexpected original PostgreSQL prefix: {prefix}')
print(build_id, revision, prefix, sep='\t')
PY
IFS=$'\t' read -r core_build_id core_revision prefix < "$work/core-provenance.tsv"
[[ ! -e "$prefix" && ! -L "$prefix" ]] || { echo "Original core prefix already exists: $prefix" >&2; exit 1; }
mkdir -p "$(dirname "$prefix")"
ln -s "$pgroot" "$prefix"
prefix_link=$prefix

source_prefix="$work/dependencies"
bash "$repo/scripts/macos/build-source-dependencies.sh" "$architecture" "$source_prefix"
export PG_MACOS_DEPENDENCY_PREFIX="$source_prefix"
export PKG_CONFIG_PATH="$source_prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export CPPFLAGS="-I$source_prefix/include${CPPFLAGS:+ $CPPFLAGS}"
export LDFLAGS="-Wl,-headerpad_max_install_names -L$source_prefix/lib${LDFLAGS:+ $LDFLAGS}"
export DYLD_LIBRARY_PATH="$source_prefix/lib${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
export MACOSX_DEPLOYMENT_TARGET=11.0
tar -xzf "$source_archive" -C "$work"
cd "$work/pgvector-$vector_version"
make PG_CONFIG="$pgroot/bin/pg_config" OPTFLAGS='-O2 -g' -j "$(sysctl -n hw.ncpu)"
make PG_CONFIG="$pgroot/bin/pg_config" OPTFLAGS= install

package="$work/package"
mkdir -p "$package/pgvector/lib" "$package/pgvector/share/extension"
library=
for candidate in vector.dylib vector.so; do
  if [[ -s "$pgroot/lib/$candidate" ]]; then
    [[ -z "$library" ]] || { echo 'Multiple pgvector modules were installed' >&2; exit 1; }
    library="$pgroot/lib/$candidate"
  fi
done
[[ -n "$library" ]] || { echo 'No pgvector module was installed' >&2; exit 1; }
cp "$library" "$package/pgvector/lib/"
cp "$pgroot/share/extension/vector"* "$package/pgvector/share/extension/"
python3 "$repo/tools/license_pointer.py" write "$package/pgvector" pgvector
python3 "$repo/scripts/macos/bundle.py" "$package/pgvector" "$architecture"
mkdir -p "$package/pgvector/LICENSES"
mv "$package/pgvector/bundled-dependencies.json" "$package/pgvector/LICENSES/pgvector-bundled-dependencies.json"
configuration="postgresql-${pg_version};pgvector-${vector_version};builder=native-macos;deployment-target=11.0;pgvector-optflags=-O2,-g;runtime=bundled-dylibs"
[[ "${GITHUB_RUN_ID:-}" =~ ^[1-9][0-9]*$ && "${GITHUB_RUN_ATTEMPT:-}" =~ ^[1-9][0-9]*$ && "${GITHUB_SHA:-}" =~ ^[0-9a-fA-F]{40}$ ]] || { echo 'Current GitHub build provenance is invalid' >&2; exit 1; }
build_id="github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
revision="$GITHUB_SHA"
core_sha=$(shasum -a 256 "$core_archive" | awk '{print $1}')
core_name=$(basename "$core_archive")
python3 - "$package/metadata.json" "$vector_version" "$build_id" "$revision" "$source_url" "$source_sha" "$configuration" "$architecture" "$core_name" "$core_sha" <<'PY'
import json, pathlib, sys
path, version, build_id, revision, url, sha, config, arch, core_name, core_sha = sys.argv[1:]
pathlib.Path(path).write_text(json.dumps({
    'project':'pgvector','version':version,'sql_names':['vector'],'requires':[],
    'configuration_prerequisites':[],'runtime_prerequisites':[], 'build_id':build_id,
    'source_revision':revision,'source_archive':{'url':url,'sha256':sha},
    'core_archive':{'basename':core_name,'sha256':core_sha},
    'build_configuration':config,'platform':'macos','architecture':arch,
}, sort_keys=True) + '\n')
PY
archive="pgvector-${vector_version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
tar -C "$package" -czf "$output/$archive" pgvector metadata.json
python3 "$repo/tools/license_pointer.py" verify "$output/$archive" pgvector
(cd "$output" && shasum -a 256 "$archive" > "$archive.sha256")

symbol_staging="$work/symbol-staging"
mkdir -p "$symbol_staging" "$output/debug-symbols"
ditto "$core_dsyms" "$symbol_staging/core"
dsymutil "$package/pgvector/lib/$(basename "$library")" -o "$symbol_staging/pgvector/vector.dylib.dSYM"
python3 "$repo/tools/create_macos_symbols.py" "$core_archive" "$output/$archive" \
  --staged-dsyms "$symbol_staging" --output-dir "$output/debug-symbols"
