#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
output=${2:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
architecture=arm64
pg_version=18.6
extension_version=1.16
source_url='https://github.com/sraoss/pg_ivm/archive/refs/tags/v1.16.tar.gz'
source_sha256=87807d6af1974fce591715d55f75d939dffea33ea6908b413e62d3dd79b9c583
core_sha256=853e0eafb3570378225d2ea16247c9de31770f85df5230509885df2ca5e89d67
core_name="postgresql-${pg_version}-macos-${architecture}.tar.gz"
extension_name="pg_ivm-${extension_version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core_archives=$(cd "$core_archives" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)

if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This feasibility probe requires native macOS $architecture" >&2
  exit 1
fi

test -s "$core_archives/$core_name" && test -s "$core_archives/$core_name.sha256"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_archives" && shasum -a 256 -c -)

work=$(mktemp -d /tmp/pgivm-macos.XXXXXX)
prefix_link_created=false
cleanup() {
  if [[ -n ${pg_ctl:-} && -n ${data_dir:-} ]]; then
    "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
  fi
  if [[ $prefix_link_created == true && -L ${prefix_link:-} ]]; then rm "$prefix_link"; fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/first" "$work/source" "$work/stage" "$work/package" \
  "$work/extracted" "$work/moved" "$work/socket"
tar -xzf "$core_archives/$core_name" -C "$work/first"
pgroot="$work/first/postgresql"
test -s "$pgroot/include/server/pg_config.h"
test -s "$pgroot/lib/pgxs/src/makefiles/pgxs.mk"

python3 - "$pgroot" > "$work/prefix" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text())
expected = {
    "component": "postgresql", "version": "18.6", "postgresql_version": "18.6",
    "platform": "macos", "architecture": "arm64", "build_id": "github-39075939632-1",
    "source_revision": "457919a19e43687a9615697a751454e3c055c593",
}
for key, value in expected.items():
    if manifest.get(key) != value:
        raise SystemExit(f"core archive manifest mismatch for {key}: {manifest.get(key)!r}")
header = (root / "include/server/pg_config.h").read_text()
match = re.search(r'#define CONFIGURE_ARGS "[^\n]*?--prefix=([^\']+)', header)
if not match:
    raise SystemExit("cannot read the original PostgreSQL installation prefix")
prefix = pathlib.Path(match.group(1))
if not re.fullmatch(r"/Users/runner/work/_temp/pg-macos-pilot\.[A-Za-z0-9]+/install/postgresql", str(prefix)):
    raise SystemExit(f"unexpected original PostgreSQL prefix: {prefix}")
print(prefix)
PY
prefix=$(cat "$work/prefix")
if [[ -e "$prefix" || -L "$prefix" ]]; then
  echo "Refusing to replace existing PostgreSQL prefix path: $prefix" >&2
  exit 1
fi
mkdir -p "$(dirname "$prefix")"
ln -s "$pgroot" "$prefix"
prefix_link=$prefix
prefix_link_created=true
pg_config="$prefix/bin/pg_config"
test "$("$pg_config" --version)" = "PostgreSQL $pg_version"
export MACOSX_DEPLOYMENT_TARGET=11.0

cd "$work/source"
curl -fL --retry 3 -o pg_ivm.tar.gz "$source_url"
printf '%s  %s\n' "$source_sha256" pg_ivm.tar.gz | shasum -a 256 -c -
test "$(tar -tzf pg_ivm.tar.gz | cut -d/ -f1 | sort -u)" = pg_ivm-1.16
tar -xzf pg_ivm.tar.gz
cd pg_ivm-1.16
test "$(sed -n "s/^default_version = '\\([^']*\\)'/\\1/p" pg_ivm.control)" = "$extension_version"
test "$(sed -n 's/^schema = \([^ ]*\)/\1/p' pg_ivm.control)" = pg_catalog
make PG_CONFIG="$pg_config" -j "$(sysctl -n hw.ncpu)"
make PG_CONFIG="$pg_config" install DESTDIR="$work/stage"

staged_root="$work/stage$(cd "$pgroot" && pwd -P)"
mkdir -p "$work/package/pg_ivm"/{lib,share/extension,bin,LICENSES}
cp "$staged_root/lib/pg_ivm.dylib" "$work/package/pg_ivm/lib/"
cp "$staged_root/share/extension/"* "$work/package/pg_ivm/share/extension/"
cp "$staged_root/bin/pg_ivm_dump_metadata" "$work/package/pg_ivm/bin/"
cp LICENSE "$work/package/pg_ivm/LICENSES/pg_ivm.txt"
cat > "$work/package/pg_ivm/LICENSES/pg_ivm-inventory.json" <<EOF
{"schema_version":1,"components":[{"component":"pg_ivm","version":"$extension_version","payload_paths":["lib/pg_ivm.dylib","share/extension","bin/pg_ivm_dump_metadata"],"license_file":"pg_ivm.txt","license_source":"https://github.com/sraoss/pg_ivm/blob/v1.16/LICENSE","source_url":"$source_url","source_sha256":"$source_sha256","redistribution_review":{"status":"resolved","basis":"The unmodified pg_ivm 1.16 source includes its full PostgreSQL-style licence notice, which permits binary redistribution when the notice, permission and disclaimer paragraphs are retained.","source_obligation":"none"}}]}
EOF
grep -Fq 'Permission to use, copy, modify, and distribute this software' LICENSE
cat > "$work/package/metadata.json" <<EOF
{"project":"pg_ivm","version":"$extension_version","sql_names":["pg_ivm"],"requires":[],"configuration_prerequisites":[{"type":"postgresql_setting","name":"shared_preload_libraries","value":"pg_ivm"}],"runtime_prerequisites":[],"postgresql_version":"$pg_version","platform":"macos","architecture":"$architecture","source":{"url":"$source_url","sha256":"$source_sha256"},"core_archive":{"basename":"$core_name","sha256":"$core_sha256"}}
EOF

tar -C "$work/package" -czf "$output/$extension_name" pg_ivm metadata.json
(cd "$output" && shasum -a 256 "$extension_name" > "$extension_name.sha256" && shasum -a 256 -c "$extension_name.sha256")
tar -xzf "$output/$extension_name" -C "$work/extracted"
extroot="$work/extracted/pg_ivm"
for relative in lib/pg_ivm.dylib bin/pg_ivm_dump_metadata; do test -x "$extroot/$relative" || test -s "$extroot/$relative"; done
test -s "$extroot/LICENSES/pg_ivm.txt"
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
    echo "pg_ivm payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv "$pgroot" "$work/moved/postgresql"
pgroot="$work/moved/postgresql"
cp -a "$extroot/." "$pgroot/"
python3 "$repo/scripts/macos/static_analysis.py" "$pgroot" "$architecture" \
  --archive "$core_archives/$core_name" --archive "$output/$extension_name" \
  --report "$output/static-analysis.json"

data_dir="$work/data"
pg_ctl="$pgroot/bin/pg_ctl"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
"$pgroot/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >/dev/null
"$pg_ctl" -D "$data_dir" -l "$work/server.log" -o \
  "-k $work/socket -p 55432 -h '' -c shared_preload_libraries=pg_ivm" -w start
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 \
  -d postgres -f "$repo/scripts/pg_ivm/probe.sql" | tee "$output/probe-output.txt"
"$pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=
pg_ctl=
echo "PASS: pg_ivm $extension_version built from unmodified upstream source, packaged, relocated, statically analysed, and exercised with PostgreSQL $pg_version on macOS $architecture"
