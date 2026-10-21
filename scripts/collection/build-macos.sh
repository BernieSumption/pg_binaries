#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: build-macos.sh CORE_ARCHIVE_DIRECTORY RESOLVED_TARGET_JSON OUTPUT_DIRECTORY}
target_json=${2:?usage: build-macos.sh CORE_ARCHIVE_DIRECTORY RESOLVED_TARGET_JSON OUTPUT_DIRECTORY}
output=${3:?usage: build-macos.sh CORE_ARCHIVE_DIRECTORY RESOLVED_TARGET_JSON OUTPUT_DIRECTORY}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core_archives=$(cd "$core_archives" && pwd)
target_json=$(cd "$(dirname "$target_json")" && pwd)/$(basename "$target_json")
mkdir -p "$output"
output=$(cd "$output" && pwd)

IFS=$'\t' read -r pg_version architecture platform core_name core_sha256 core_build_id core_source_revision source_1_1_1 source_2_1_3 <<< "$(PYTHONPATH="$repo/tools" python3 - "$target_json" <<'PY'
import sys
from collection_macos_target import load_target, VERSIONS
target = load_target(sys.argv[1], require_resolved=True)
print("\t".join((target.postgresql_version, target.architecture, target.platform,
                 target.core_basename, target.core_sha256, target.core_build_id,
                 target.core_source_revision, VERSIONS["1.1.1"], VERSIONS["2.1.3"])))
PY
)"

if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "Collection build requires native macOS $architecture" >&2
  exit 1
fi
test -s "$core_archives/$core_name" && test -s "$core_archives/$core_name.sha256"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_archives" && shasum -a 256 -c -)

work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/collection-build.XXXXXX")
prefix_link_created=false
cleanup() {
  if [[ $prefix_link_created == true && -n ${prefix_link:-} && -L $prefix_link ]]; then rm "$prefix_link"; fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/core" "$work/source" "$work/stage"
tar -xzf "$core_archives/$core_name" -C "$work/core"
pgroot="$work/core/postgresql"
test -s "$pgroot/include/server/pg_config.h"
test -s "$pgroot/lib/pgxs/src/makefiles/pgxs.mk"
python3 - "$pgroot" "$architecture" "$pg_version" "$core_build_id" "$core_source_revision" > "$work/prefix" <<'PY'
import json, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
architecture, version, build_id, revision = sys.argv[2:]
manifest = json.loads((root / "manifest.json").read_text())
expected = {"component":"postgresql", "version":version, "postgresql_version":version,
            "platform":"macos", "architecture":architecture, "build_id":build_id,
            "source_revision":revision}
for key, value in expected.items():
    if manifest.get(key) != value:
        raise SystemExit(f"core manifest mismatch for {key}")
header = (root / "include/server/pg_config.h").read_text()
match = re.search(r'#define CONFIGURE_ARGS "[^\n]*?--prefix=([^\']+)', header)
if not match:
    raise SystemExit("cannot read the PostgreSQL installation prefix")
prefix = pathlib.Path(match.group(1))
if not re.fullmatch(r"/Users/runner/work/_temp/pg-macos-pilot\.[A-Za-z0-9]+/install/postgresql", str(prefix)):
    raise SystemExit(f"unexpected original PostgreSQL prefix: {prefix}")
print(prefix)
PY
prefix=$(cat "$work/prefix")
if [[ -e "$prefix" || -L "$prefix" ]]; then echo "Refusing to replace existing PostgreSQL prefix: $prefix" >&2; exit 1; fi
mkdir -p "$(dirname "$prefix")"
ln -s "$pgroot" "$prefix"
prefix_link=$prefix
prefix_link_created=true
pg_config="$prefix/bin/pg_config"
test "$("$pg_config" --version)" = "PostgreSQL $pg_version"
export MACOSX_DEPLOYMENT_TARGET=11.0

build_one() {
  local version=$1 source_sha256=$2
  local source_url="https://github.com/aws/pgcollection/archive/refs/tags/v${version}.tar.gz"
  local source_archive="pgcollection-v${version}.tar.gz"
  local source_dir="$work/source/${version}"
  local package="$work/package/${version}"
  local archive="collection-${version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
  mkdir -p "$source_dir" "$package/collection/lib" "$package/collection/share/extension"
  curl -fL --retry 3 -o "$work/source/$source_archive" "$source_url"
  printf '%s  %s\n' "$source_sha256" "$work/source/$source_archive" | shasum -a 256 -c -
  test "$(tar -tzf "$work/source/$source_archive" | cut -d/ -f1 | sort -u)" = "pgcollection-${version}"
  tar -xzf "$work/source/$source_archive" -C "$source_dir"
  local source_root="$source_dir/pgcollection-${version}"
  test -f "$source_root/Makefile"
  test -f "$source_root/collection.control.in" || test -f "$source_root/collection.control"
  test "$(sed -n 's/^EXTVERSION = //p' "$source_root/Makefile")" = "$version"
  make -C "$source_root" PG_CONFIG="$pg_config" PG_LDFLAGS='-Wl,-rpath,@loader_path' -j "$(sysctl -n hw.ncpu)"
  make -C "$source_root" PG_CONFIG="$pg_config" install DESTDIR="$work/stage/${version}"
  local staged_root="$work/stage/${version}$(cd "$pgroot" && pwd -P)"
  local module_file
  module_file=$(find "$staged_root/lib" -maxdepth 1 -type f \( -name 'collection.dylib' -o -name 'collection.so' \) -print)
  test -n "$module_file" && test "$(printf '%s\n' "$module_file" | wc -l | tr -d ' ')" = 1 && test -s "$module_file"
  local module_name=${module_file##*/}
  cp "$module_file" "$package/collection/lib/"
  cp "$staged_root/share/extension/collection"* "$package/collection/share/extension/"
  python3 "$repo/tools/license_pointer.py" write "$package/collection" collection
  python3 - "$package" "$version" "$pg_version" "$architecture" "$source_url" "$source_sha256" "$core_name" "$core_sha256" "$module_name" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
version, pg_version, architecture, url, sha256, core_name, core_sha256, module_name = sys.argv[2:]
module_path = "lib/" + module_name
metadata = {"project":"collection", "version":version, "sql_names":["collection"],
            "requires":[], "configuration_prerequisites":[], "runtime_prerequisites":[],
            "postgresql_version":pg_version, "platform":"macos", "architecture":architecture,
            "source":{"url":url, "sha256":sha256},
            "core_archive":{"basename":core_name, "sha256":core_sha256}}
(root / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

PY
  tar -C "$package" -czf "$output/$archive" collection metadata.json
  python3 "$repo/tools/license_pointer.py" verify "$output/$archive" collection
  (cd "$output" && shasum -a 256 "$archive" > "$archive.sha256" && shasum -a 256 -c "$archive.sha256")
  python3 - "$output/$archive" "$version" "$architecture" "$pg_version" "$core_name" "$core_sha256" <<'PY'
import json, pathlib, sys, tarfile
archive = pathlib.Path(sys.argv[1])
version, architecture, pg_version, core_name, core_sha256 = sys.argv[2:]
with tarfile.open(archive, "r:gz") as tar:
    names = set(tar.getnames())
    modules = names & {"collection/lib/collection.dylib", "collection/lib/collection.so"}
    expected_names = {"collection", "collection/lib", *modules, "collection/share",
        "collection/share/extension", *[n for n in names if n.startswith("collection/share/extension/")],
        "collection/LICENSES", "collection/LICENSES/collection/LICENCE", "metadata.json"}
    if len(modules) != 1 or names != expected_names:
        raise SystemExit("collection archive has missing or unexpected members")
    metadata = json.load(tar.extractfile("metadata.json"))
    expected = {"project":"collection", "version":version, "sql_names":["collection"],
        "requires":[], "configuration_prerequisites":[], "runtime_prerequisites":[],
        "postgresql_version":pg_version, "platform":"macos", "architecture":architecture,
        "source":{"url":f"https://github.com/aws/pgcollection/archive/refs/tags/v{version}.tar.gz",
                  "sha256":{"1.1.1":"ab99a969334442e4a3c77405bc9ffed0083595d18f3898d64a731353a32bec5e",
                            "2.1.3":"a6b07864e5893d3b682bb3223fd6d33015709765c9d40d415c85112358f0e3e4"}[version]},
        "core_archive":{"basename":core_name,"sha256":core_sha256}}
    if metadata != expected:
        raise SystemExit("collection archive metadata identity mismatch")
PY
  python3 "$repo/tools/check_extension_redistribution.py" "$output/$archive"
}

build_one 1.1.1 "$source_1_1_1"
build_one 2.1.3 "$source_2_1_3"
echo "PASS: packaged collection 1.1.1 and 2.1.3 for PostgreSQL $pg_version on macOS $architecture"
