#!/usr/bin/env bash
set -euo pipefail

pg_version=${3:-18.6}
vector_version=0.8.7
architecture=${2:-$(uname -m)}
script_dir=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$script_dir/../.." && pwd)
output_dir=$(mkdir -p "${1:?output directory required}" && cd "$1" && pwd)
work_dir=$(mktemp -d "${RUNNER_TEMP:-/tmp}/pg-macos-pilot.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT

source_revision=${SOURCE_REVISION:-${GITHUB_SHA:-}}
if [[ -z $source_revision ]]; then
  source_revision=$(git -C "$repo" rev-parse HEAD 2>/dev/null || true)
fi
if [[ ! $source_revision =~ ^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$ ]]; then
  echo "SOURCE_REVISION must be a full Git object ID: $source_revision" >&2
  exit 2
fi
build_id=${BUILD_ID:-}
if [[ -z $build_id ]]; then
  if [[ -n ${GITHUB_RUN_ID:-} ]]; then
    build_id="github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT:-1}"
  else
    build_id="local-$(python3 -c 'import uuid; print(uuid.uuid4())')"
  fi
fi
if [[ ! $build_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "BUILD_ID may contain only letters, digits, dot, underscore and hyphen" >&2
  exit 2
fi

if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This build requires native macOS $architecture" >&2
  exit 1
fi
case "$architecture" in
  x86_64) platform_arch=x86_64 ;;
  arm64) platform_arch=arm64 ;;
  *) echo "Unsupported macOS architecture: $architecture" >&2; exit 1 ;;
esac
build_configuration="postgresql-${pg_version};pgvector-${vector_version};builder=native-macos;deployment-target=11.0;configure=icu,openssl,lz4,zstd,libxml,libxslt,zlib,uuid-e2fs,no-readline;dependencies=pinned-upstream-source-with-homebrew-uuid;cflags=-O2,-g;pgvector-optflags=-O2,-g;runtime=bundled-dylibs"

brew install e2fsprogs
uuid_prefix=$(brew --prefix e2fsprogs)
source_prefix="$work_dir/dependencies"
bash "$script_dir/build-source-dependencies.sh" "$architecture" "$source_prefix"
export PG_MACOS_DEPENDENCY_PREFIX="$source_prefix"
export PKG_CONFIG_PATH="$source_prefix/lib/pkgconfig:$uuid_prefix/lib/pkgconfig"
export CPPFLAGS="-I$source_prefix/include -I$uuid_prefix/include"
export LDFLAGS="-Wl,-headerpad_max_install_names -L$source_prefix/lib -L$uuid_prefix/lib"
export MACOSX_DEPLOYMENT_TARGET=11.0

curl -fL --retry 3 "https://ftp.postgresql.org/pub/source/v${pg_version}/postgresql-${pg_version}.tar.bz2" -o "$work_dir/postgresql.tar.bz2"
curl -fL --retry 3 "https://github.com/pgvector/pgvector/archive/refs/tags/v${vector_version}.tar.gz" -o "$work_dir/pgvector.tar.gz"
tar -xjf "$work_dir/postgresql.tar.bz2" -C "$work_dir"
tar -xzf "$work_dir/pgvector.tar.gz" -C "$work_dir"

install_dir="$work_dir/install/postgresql"
cd "$work_dir/postgresql-${pg_version}"
CFLAGS='-O2 -g' ./configure --prefix="$install_dir" --with-icu --with-ssl=openssl --with-lz4 --with-zstd --with-libxml --with-libxslt --with-zlib --with-uuid=e2fs --without-readline
make -j "$(sysctl -n hw.ncpu)"
make -C contrib -j "$(sysctl -n hw.ncpu)"
make install
make -C contrib install

package_dir="$work_dir/package"
mkdir -p "$package_dir/postgresql/LICENSES" "$package_dir/pgvector/lib" "$package_dir/pgvector/share/extension" "$package_dir/pgvector/LICENSES"
cp -R "$install_dir"/. "$package_dir/postgresql/"
cp "$work_dir/postgresql-${pg_version}/COPYRIGHT" "$package_dir/postgresql/LICENSES/PostgreSQL.txt"
python3 "$script_dir/bundle.py" "$package_dir/postgresql" "$architecture"
python3 "$script_dir/licenses.py" "$package_dir/postgresql" "$source_prefix/share/pg_binaries/source-dependencies.json"
builtins=$(python3 "$script_dir/../../tools/discover_builtins.py" "$package_dir/postgresql")

cat > "$package_dir/postgresql/manifest.json" <<EOF
{
  "schema_version": 1,
  "component": "postgresql",
  "version": "$pg_version",
  "postgresql_version": "$pg_version",
  "platform": "macos",
  "architecture": "$platform_arch",
  "build_id": "$build_id",
  "source_revision": "$source_revision",
  "build_configuration": "$build_configuration",
  "included_extensions": $builtins,
  "capabilities": ["icu", "libc_collations", "lz4", "zstd_wal"]
}
EOF

cd "$work_dir/pgvector-${vector_version}"
make PG_CONFIG="$install_dir/bin/pg_config" OPTFLAGS='-O2 -g' -j "$(sysctl -n hw.ncpu)"
make PG_CONFIG="$install_dir/bin/pg_config" OPTFLAGS= install
cp "$install_dir/lib/vector.dylib" "$package_dir/pgvector/lib/"
cp "$install_dir/share/extension/vector"* "$package_dir/pgvector/share/extension/"
cp LICENSE "$package_dir/pgvector/LICENSES/pgvector.txt"
python3 "$script_dir/bundle.py" "$package_dir/pgvector" "$architecture"
python3 "$script_dir/licenses.py" "$package_dir/pgvector"
mv "$package_dir/pgvector/bundled-dependencies.json" "$package_dir/pgvector/LICENSES/pgvector-bundled-dependencies.json"
mv "$package_dir/pgvector/LICENSES/inventory.json" "$package_dir/pgvector/LICENSES/pgvector-dependency-inventory.json"

cat > "$package_dir/metadata.json" <<EOF
{"project":"pgvector","version":"${vector_version}","sql_names":["vector"],"requires":[],"configuration_prerequisites":[],"runtime_prerequisites":[],"build_id":"${build_id}","source_revision":"${source_revision}","build_configuration":"${build_configuration}","platform":"macos","architecture":"${platform_arch}"}
EOF

python3 - "$package_dir" > "$work_dir/macho-paths.bin" <<'PY'
import json
import pathlib
import subprocess
import sys

package = pathlib.Path(sys.argv[1])
for component in ("postgresql", "pgvector"):
    root = package / component
    dependency_file = root / ("bundled-dependencies.json" if component == "postgresql" else "LICENSES/pgvector-bundled-dependencies.json")
    external = set(json.loads(dependency_file.read_text()))
    for directory in ("bin", "lib", "libexec"):
        if component == "pgvector" and directory != "lib":
            continue
        candidate_dir = root / directory
        if not candidate_dir.exists():
            continue
        for path in sorted(candidate_dir.rglob("*")):
            if not path.is_file() or path.is_symlink() or path.name in external or path.suffix == ".a":
                continue
            if subprocess.run(("lipo", "-archs", str(path)), capture_output=True).returncode == 0:
                sys.stdout.buffer.write(str(path).encode() + b"\0")
PY
dsyms="$work_dir/dsyms"
while IFS= read -r -d '' binary; do
  relative=${binary#"$package_dir"/}
  mkdir -p "$dsyms/$(dirname "$relative")"
  dsymutil "$binary" -o "$dsyms/$relative.dSYM"
done < "$work_dir/macho-paths.bin"

pg_archive="postgresql-${pg_version}-macos-${platform_arch}.tar.gz"
vector_archive="pgvector-${vector_version}-postgresql-${pg_version}-macos-${platform_arch}.tar.gz"
tar -C "$package_dir" -czf "$output_dir/$pg_archive" postgresql
tar -C "$package_dir" -czf "$output_dir/$vector_archive" pgvector metadata.json
cd "$output_dir"
shasum -a 256 "$pg_archive" > "$pg_archive.sha256"
shasum -a 256 "$vector_archive" > "$vector_archive.sha256"
python3 "$script_dir/../../tools/create_macos_symbols.py" \
  "$output_dir/$pg_archive" "$output_dir/$vector_archive" \
  --staged-dsyms "$dsyms" --output-dir "$output_dir/debug-symbols"
ls -lh "$pg_archive" "$vector_archive"
