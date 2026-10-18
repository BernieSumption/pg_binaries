#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY [TARGET_CONFIG]}
output=${2:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY [TARGET_CONFIG]}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
target_config=${3:-$repo/tools/hypopg_macos_pins/18.6-arm64.json}
target_values=$(PYTHONPATH="$repo/tools" python3 - "$target_config" <<'PY'
import sys
from hypopg_macos_target import load_target_config

target = load_target_config(sys.argv[1])
print("\t".join(target.shell_values()))
PY
)
IFS=$'\t' read -r pg_version architecture platform profile_id core_name core_run_id core_sha256 core_build_id core_source_revision source_url source_sha256 <<< "$target_values"
hypopg_version=1.4.3
extension_name="hypopg-${hypopg_version}-postgresql-${pg_version}-${platform}.tar.gz"
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

work=$(mktemp -d /tmp/hypopg-macos.XXXXXX)
prefix_link_created=false
cleanup() {
  if [[ -n ${pg_ctl:-} && -n ${data_dir:-} ]]; then
    "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
  fi
  if [[ $prefix_link_created == true && -n ${prefix_link:-} && -L $prefix_link ]]; then
    rm "$prefix_link"
  fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/first" "$work/source" "$work/stage" "$work/extension" "$work/moved" "$work/socket"
tar -xzf "$core_archives/$core_name" -C "$work/first"
pgroot="$work/first/postgresql"
test -s "$pgroot/include/server/pg_config.h"
test -s "$pgroot/lib/pgxs/src/makefiles/pgxs.mk"

python3 - "$pgroot" "$pg_version" "$architecture" "$core_build_id" "$core_source_revision" <<'PY' > "$work/prefix"
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text())
expected = {
    "component": "postgresql", "version": sys.argv[2], "postgresql_version": sys.argv[2],
    "platform": "macos", "architecture": sys.argv[3], "build_id": sys.argv[4],
    "source_revision": sys.argv[5],
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
curl -fL --retry 3 -o hypopg.tar.gz "$source_url"
printf '%s  %s\n' "$source_sha256" hypopg.tar.gz | shasum -a 256 -c -
test "$(tar -tzf hypopg.tar.gz | cut -d/ -f1 | sort -u)" = "hypopg-$hypopg_version"
tar -xzf hypopg.tar.gz
cd "hypopg-$hypopg_version"
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" hypopg.control)" = "$hypopg_version"
make USE_PGXS=1 PG_CONFIG="$pg_config" -j "$(sysctl -n hw.ncpu)"
make USE_PGXS=1 PG_CONFIG="$pg_config" install DESTDIR="$work/stage"

staged_root="$work/stage$(cd "$pgroot" && pwd -P)"
package="$work/package"
mkdir -p "$package/hypopg/lib" "$package/hypopg/share/extension" "$package/hypopg/LICENSES"
test -s "$staged_root/lib/hypopg.dylib"
cp "$staged_root/lib/hypopg.dylib" "$package/hypopg/lib/"
cp "$staged_root/share/extension/"* "$package/hypopg/share/extension/"
cp LICENSE "$package/hypopg/LICENSES/HypoPG.txt"
python3 - "$package" "$hypopg_version" "$source_url" "$source_sha256" <<'PY'
import json
import pathlib
import sys

package = pathlib.Path(sys.argv[1]) / "hypopg"
payload_paths = sorted(
    path.relative_to(package).as_posix()
    for path in package.rglob("*")
    if (path.is_file() or path.is_symlink()) and "LICENSES" not in path.relative_to(package).parts
)
inventory = {
    "schema_version": 1,
    "components": [{
        "component": "hypopg", "version": sys.argv[2],
        "payload_paths": payload_paths, "license_file": "HypoPG.txt",
        "license_source": "https://github.com/HypoPG/hypopg/tree/1.4.3/LICENSE",
        "source_url": sys.argv[3], "source_sha256": sys.argv[4],
        "redistribution_review": {
            "status": "resolved",
            "basis": "The unmodified HypoPG 1.4.3 source archive includes this PostgreSQL License text for the project. It permits redistribution for any purpose provided the copyright notice, permission paragraph and disclaimer paragraphs remain in copies; this archive retains the complete upstream LICENSE text.",
            "source_obligation": "none",
        },
    }],
}
(package / "LICENSES/hypopg-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
PY
cat > "$package/metadata.json" <<EOF
{"project":"hypopg","version":"$hypopg_version","sql_names":["hypopg"],"requires":[],"configuration_prerequisites":[],"runtime_prerequisites":[],"postgresql_version":"$pg_version","platform":"macos","architecture":"$architecture","source":{"url":"$source_url","sha256":"$source_sha256"},"core_archive":{"basename":"$core_name","sha256":"$core_sha256"}}
EOF

tar -C "$package" -czf "$output/$extension_name" hypopg metadata.json
cd "$output"
shasum -a 256 "$extension_name" > "$extension_name.sha256"
shasum -a 256 -c "$extension_name.sha256"
python3 "$repo/tools/check_macos_extension_license_inventory.py" "$output/$extension_name"
tar -xzf "$extension_name" -C "$work/extension"
extroot="$work/extension/hypopg"
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then
      continue
    fi
    echo "HypoPG payload collision: $relative" >&2
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
"$pg_ctl" -D "$data_dir" -l "$work/server.log" -o "-k $work/socket -p 55432 -h ''" -w start
"$pgroot/bin/psql" -X -A -t -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 \
  -v expected_pg_major="${pg_version%%.*}" \
  -d postgres -f "$repo/scripts/hypopg/macos-probe.sql" | tee "$output/probe-output.txt"
grep -Eq '^t$' "$output/probe-output.txt"
grep -Eq '^Index Scan using .*btree_hypo_probe_id' "$output/probe-output.txt"
grep -Eq '^0$' "$output/probe-output.txt"
"$pgroot/bin/pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=
pg_ctl=
echo "PASS: HypoPG $hypopg_version built from upstream source, relocated, statically analysed, and exercised with PostgreSQL $pg_version on macOS $architecture"
