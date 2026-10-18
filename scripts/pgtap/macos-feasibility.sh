#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
output=${2:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
target_config=${3:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY TARGET_CONFIG}
build_only=${4:-}
if [[ -n $build_only && $build_only != --build-only ]]; then
  echo "Unknown option: $build_only" >&2
  exit 2
fi
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
source "$repo/scripts/macos/core-prefix.sh"
if [[ $target_config != /* ]]; then
  target_config="$repo/$target_config"
fi
target_values=$(python3 - "$repo/tools" "$target_config" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from pgtap_macos_target import load_target_config
print("\t".join(load_target_config(sys.argv[2]).shell_values()))
PY
)
IFS=$'\t' read -r pg_version version architecture platform profile_id core_name core_run_id \
  core_sha256 core_build_id core_source_revision source_url source_sha256 <<< "$target_values"
extension_name="pgtap-${version}-postgresql-${pg_version}-${platform}.tar.gz"
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
  macos_remove_core_prefix
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/first" "$work/source" "$work/stage" "$work/extension" "$work/moved" "$work/socket"
tar -xzf "$core_archives/$core_name" -C "$work/first"
pgroot="$work/first/postgresql"
test -s "$pgroot/include/server/pg_config.h"
test -s "$pgroot/lib/pgxs/src/makefiles/pgxs.mk"

prefix=$(macos_core_prefix_from_archive "$pgroot" "$pg_version" "$architecture" "$core_build_id" "$core_source_revision")
macos_restore_core_prefix "$prefix" "$pgroot"
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
python3 "$repo/tools/check_extension_redistribution.py" "$output/$extension_name"
if [[ $build_only == --build-only ]]; then
  echo "PASS: pgTAP $version archive packaged and checked for PostgreSQL $pg_version on macOS $architecture"
  exit 0
fi
tar -xzf "$extension_name" -C "$work/extension"
extroot="$work/extension/pgtap"
python3 - "$work/extension" "$extroot" "$pg_version" "$version" "$architecture" <<'PY'
import json
import pathlib
import sys

root, payload = map(pathlib.Path, sys.argv[1:3])
pg_version, version, architecture = sys.argv[3:]
if {p.name for p in root.iterdir()} != {"pgtap", "metadata.json"}:
    raise SystemExit("pgTAP archive must contain only pgtap and metadata.json")
meta = json.loads((root / "metadata.json").read_text())
if (meta.get("project"), meta.get("version"), meta.get("sql_names"), meta.get("postgresql_version"), meta.get("platform"), meta.get("architecture")) != ("pgtap", version, ["pgtap"], pg_version, "macos", architecture):
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
echo "PASS: pgTAP $version source package installed, relocated, statically analysed, and exercised with PostgreSQL $pg_version on macOS $architecture using $profile_id core run $core_run_id"
