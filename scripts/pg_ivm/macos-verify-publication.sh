#!/usr/bin/env bash
set -euo pipefail

target_json=${1:?usage: macos-verify-publication.sh TARGET_JSON CORE_DIR ARCHIVE_DIR OUTPUT_DIR}
core_dir=${2:?usage: macos-verify-publication.sh TARGET_JSON CORE_DIR ARCHIVE_DIR OUTPUT_DIR}
archive_dir=${3:?usage: macos-verify-publication.sh TARGET_JSON CORE_DIR ARCHIVE_DIR OUTPUT_DIR}
output=${4:?usage: macos-verify-publication.sh TARGET_JSON CORE_DIR ARCHIVE_DIR OUTPUT_DIR}
mode=${5:-all}
case "$mode" in static-analysis|archive-suite|all) ;; *) echo "unknown verification mode: $mode" >&2; exit 2 ;; esac
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
target_json=$(cd "$(dirname "$target_json")" && pwd)/$(basename "$target_json")
core_dir=$(cd "$core_dir" && pwd)
archive_dir=$(cd "$archive_dir" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
read -r pg_version architecture core_name core_sha256 <<<"$(python3 - "$target_json" <<'PY'
import json, re, sys
from pathlib import Path
t=json.loads(Path(sys.argv[1]).read_text()); v=t.get("postgresql_version"); a=t.get("architecture"); c=t.get("core_archive",{})
if v not in {"17.11","18.6"} or a not in {"arm64","x86_64"} or t.get("platform") != f"macos-{a}": raise SystemExit("unsupported pg_ivm target")
if c.get("basename") != f"postgresql-{v}-macos-{a}.tar.gz" or not re.fullmatch(r"[0-9a-f]{64}",str(c.get("sha256",""))): raise SystemExit("target does not bind the exact core archive")
print(v,a,c["basename"],c["sha256"])
PY
)"
extension="pg_ivm-1.16-postgresql-${pg_version}-macos-${architecture}.tar.gz"
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then echo "Verification requires native macOS $architecture" >&2; exit 1; fi
for path in "$core_dir/$core_name" "$archive_dir/$extension"; do test -s "$path" && test -s "$path.sha256"; (cd "$(dirname "$path")" && shasum -a 256 -c "$(basename "$path").sha256"); done
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_dir" && shasum -a 256 -c -)
work=$(mktemp -d /tmp/pgivm-verify.XXXXXX)
prefix_link_created=false
cleanup() {
  if [[ -n ${pg_ctl:-} && -n ${data_dir:-} ]]; then "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true; fi
  if [[ $prefix_link_created == true && -L ${prefix_link:-} ]]; then rm "$prefix_link"; fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/first" "$work/extracted" "$work/moved" "$work/socket"
tar -xzf "$core_dir/$core_name" -C "$work/first"
pgroot="$work/first/postgresql"
test -s "$pgroot/include/server/pg_config.h" && test -s "$pgroot/lib/pgxs/src/makefiles/pgxs.mk"
python3 - "$pgroot" "$target_json" <<'PY'
import json,pathlib,sys
r=pathlib.Path(sys.argv[1]); t=json.loads(pathlib.Path(sys.argv[2]).read_text()); m=json.loads((r/'manifest.json').read_text())
expected={"component":"postgresql","version":t["postgresql_version"],"postgresql_version":t["postgresql_version"],"platform":"macos","architecture":t["architecture"]}
if any(m.get(k)!=v for k,v in expected.items()): raise SystemExit("core manifest differs from selected target")
PY
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
python3 - "$archive_dir/$extension" "$target_json" <<'PY'
import json,sys,tarfile
from pathlib import Path
t=json.loads(Path(sys.argv[2]).read_text()); core=t.get("core_archive",{}); expected={"project":"pg_ivm","version":"1.16","sql_names":["pg_ivm"],"postgresql_version":t["postgresql_version"],"platform":"macos","architecture":t["architecture"],"core_archive":{"basename":core.get("basename"),"sha256":core.get("sha256")}}
with tarfile.open(sys.argv[1],"r:gz") as a:
 m=next((x for x in a.getmembers() if x.name=="metadata.json" and x.isfile() and x.size<=1048576),None)
 if m is None: raise SystemExit("extension archive has no bounded metadata")
 value=json.load(a.extractfile(m))
if any(value.get(k)!=v for k,v in expected.items()): raise SystemExit("extension metadata differs from selected target")
PY
tar -xzf "$archive_dir/$extension" -C "$work/extracted"
extroot="$work/extracted/pg_ivm"
test -s "$extroot/lib/pg_ivm.dylib" && test -s "$extroot/LICENSES/pg_ivm.txt"
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}; destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
    echo "pg_ivm payload collision: $relative" >&2; exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv "$pgroot" "$work/moved/postgresql"
pgroot="$work/moved/postgresql"
cp -a "$extroot/." "$pgroot/"
if [[ $mode == static-analysis || $mode == all ]]; then
  python3 "$repo/scripts/macos/static_analysis.py" "$pgroot" "$architecture" --archive "$core_dir/$core_name" --archive "$archive_dir/$extension" --report "$output/static-analysis.json"
fi
if [[ $mode == static-analysis ]]; then
  echo "PASS: fresh-runner static analysis passed for PostgreSQL $pg_version macOS $architecture"
  exit 0
fi
data_dir="$work/data"
pg_ctl="$pgroot/bin/pg_ctl"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
"$pgroot/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >/dev/null
"$pg_ctl" -D "$data_dir" -l "$work/server.log" -o "-k $work/socket -p 55432 -h '' -c shared_preload_libraries=pg_ivm" -w start
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 -d postgres -f "$repo/scripts/pg_ivm/probe.sql" | tee "$output/probe-output.txt"
"$pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=
pg_ctl=
echo "PASS: fresh-runner pg_ivm archive suite passed for PostgreSQL $pg_version macOS $architecture"
