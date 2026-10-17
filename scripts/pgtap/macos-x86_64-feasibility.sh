#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-x86_64-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
output=${2:?usage: macos-x86_64-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
architecture=x86_64
pg_version=18.6
version=1.3.4
source_url='https://github.com/theory/pgtap/archive/refs/tags/v1.3.4.tar.gz'
source_sha256=d2c951afb296a001d21785611a8e966e3f8fa3f5bfbd929396a5130c0152f314
core_sha256=36a2f9297d05b88125c697a6e2f73ee61ae2b3ae9edbd95d20ed3d42ffa6e91f
core_name="postgresql-${pg_version}-macos-${architecture}.tar.gz"
extension_name="pgtap-${version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
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

work=$(mktemp -d /tmp/pgtap-macos.XXXXXX)
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

python3 - "$pgroot" > "$work/prefix" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text())
expected = {
    "component": "postgresql", "version": "18.6", "postgresql_version": "18.6",
    "platform": "macos", "architecture": "x86_64", "build_id": "github-39068360742-1",
    "source_revision": "3a600990f3deed8e32c57b249c31653d319b50b2",
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

cd "$work/source"
curl -fL --retry 3 -o pgtap.tar.gz "$source_url"
printf '%s  %s\n' "$source_sha256" pgtap.tar.gz | shasum -a 256 -c -
test "$(tar -tzf pgtap.tar.gz | cut -d/ -f1 | sort -u)" = "pgtap-$version"
tar -xzf pgtap.tar.gz
cd "pgtap-$version"
test "$(sed -n "s/^default_version = '\\([^']*\\)'/\\1/p" pgtap.control)" = "$version"
make USE_PGXS=1 PG_CONFIG="$pg_config"
make USE_PGXS=1 PG_CONFIG="$pg_config" install DESTDIR="$work/stage"

staged_share="$work/stage$(cd "$pgroot/share" && pwd -P)"
package="$work/package"
mkdir -p "$package/pgtap/share/extension" "$package/pgtap/share/doc/extension" "$package/pgtap/LICENSES"
cp "$staged_share/extension/"* "$package/pgtap/share/extension/"
cp -a "$staged_share/doc/extension/." "$package/pgtap/share/doc/extension/"
sed -n '/^Copyright and License$/,$p' README.md | sed '1,2d' > "$package/pgtap/LICENSES/pgTAP.txt"
grep -Fxq 'Copyright (c) 2008-2025 David E. Wheeler. Some rights reserved.' "$package/pgtap/LICENSES/pgTAP.txt"
cat > "$package/pgtap/LICENSES/pgtap-inventory.json" <<EOF
{
  "schema_version": 1,
  "components": [{
    "component": "pgtap", "version": "$version",
    "payload_paths": ["share/extension", "share/doc/extension"],
    "license_file": "pgTAP.txt",
    "license_source": "https://github.com/theory/pgtap/tree/v$version",
    "redistribution_review": {
      "status": "resolved",
      "basis": "The pgTAP v$version source distribution applies the included permissive copyright notice to the project files and generated SQL and documentation payload. The notice permits redistribution with its attribution and disclaimer retained.",
      "source_obligation": "none"
    }
  }]
}
EOF
cat > "$package/metadata.json" <<EOF
{"project":"pgtap","version":"$version","sql_names":["pgtap"],"requires":[],"configuration_prerequisites":[{"type":"sql_extension","name":"plpgsql","value":"CREATE EXTENSION plpgsql"}],"runtime_prerequisites":[],"postgresql_version":"$pg_version","platform":"macos","architecture":"$architecture","source":{"url":"$source_url","sha256":"$source_sha256"},"core_archive":{"basename":"$core_name","sha256":"$core_sha256"}}
EOF

tar -C "$package" -czf "$output/$extension_name" pgtap metadata.json
cd "$output"
shasum -a 256 "$extension_name" > "$extension_name.sha256"
shasum -a 256 -c "$extension_name.sha256"
tar -xzf "$extension_name" -C "$work/extension"
extroot="$work/extension/pgtap"
python3 - "$work/extension" "$extroot" <<'PY'
import json
import pathlib
import sys

root, payload = map(pathlib.Path, sys.argv[1:])
if {p.name for p in root.iterdir()} != {"pgtap", "metadata.json"}:
    raise SystemExit("pgTAP archive must contain only pgtap and metadata.json")
meta = json.loads((root / "metadata.json").read_text())
if (meta.get("project"), meta.get("version"), meta.get("sql_names"), meta.get("platform"), meta.get("architecture")) != ("pgtap", "1.3.4", ["pgtap"], "macos", "x86_64"):
    raise SystemExit("pgTAP package metadata identity mismatch")
required = ["pgtap--1.3.4.sql", "pgtap-core--1.3.4.sql", "pgtap-schema--1.3.4.sql", "pgtap--1.3.3--1.3.4.sql"]
sql = payload / "share/extension"
if {p.stem for p in sql.glob("*.control")} != {"pgtap"}:
    raise SystemExit("package must expose exactly the pgtap extension identity")
for name in required:
    if not (sql / name).is_file():
        raise SystemExit(f"pgTAP installed SQL file missing: {name}")
if not (payload / "share/doc/extension/pgtap.mmd").is_file():
    raise SystemExit("pgTAP installed documentation missing")
if not (payload / "LICENSES/pgTAP.txt").is_file() or not (payload / "LICENSES/pgtap-inventory.json").is_file():
    raise SystemExit("pgTAP licence payload missing")
if any(p.suffix in {".so", ".dylib", ".dll"} for p in payload.rglob("*")):
    raise SystemExit("pgTAP SQL-only payload unexpectedly contains a native library")
PY
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then
      continue
    fi
    echo "pgTAP payload collision: $relative" >&2
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
  -d postgres -f "$repo/scripts/pgtap/probe.sql" | tee "$output/probe-output.txt"
grep -Fxq '1..4' "$output/probe-output.txt"
test "$(grep -Ec '^ok [1-4]( -|$)' "$output/probe-output.txt")" -eq 4
"$pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=
pg_ctl=
echo "PASS: pgTAP $version source package installed, relocated, statically analysed, and exercised with PostgreSQL $pg_version on macOS $architecture"
