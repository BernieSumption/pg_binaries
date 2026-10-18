#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY [arm64|x86_64]}
output=${2:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY [arm64|x86_64]}
architecture=${3:-arm64}
pg_version=18.6
extension_version=1.6.8
source_url='https://github.com/citusdata/pg_cron/archive/refs/tags/v1.6.8.tar.gz'
source_sha256=c19ab9bb35406c60fb51ecda993737c083850abe424acb6c1030439d00a1f8e4
case "$architecture" in
  arm64) core_sha256=bc543b0d54a8a33b3b737eab74d7f185035f01e5c2db4eb48be049996eee4440; core_build_id=github-39079982683-1 ;;
  x86_64) core_sha256=5ec45e48bad1439860f0143fd6f2cbc04a86cfa456beef8c5ca9040960ea3f40; core_build_id=github-39079982747-1 ;;
  *) echo "Unsupported macOS architecture: $architecture" >&2; exit 2 ;;
esac
core_name="postgresql-${pg_version}-macos-${architecture}.tar.gz"
extension_name="pg_cron-${extension_version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
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

work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/pgcron-macos.XXXXXX")
prefix_link_created=false
cleanup() {
  if [[ -n ${pg_ctl:-} && -n ${data_dir:-} ]]; then
    "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
  fi
  if [[ $prefix_link_created == true && -L ${prefix_link:-} ]]; then rm "$prefix_link"; fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/first" "$work/source" "$work/stage" "$work/package" "$work/extracted" "$work/moved" "$work/socket"
tar -xzf "$core_archives/$core_name" -C "$work/first"
pgroot="$work/first/postgresql"
test -s "$pgroot/include/server/pg_config.h"
test -s "$pgroot/lib/pgxs/src/makefiles/pgxs.mk"

python3 - "$pgroot" "$architecture" "$core_build_id" > "$work/prefix" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
architecture, core_build_id = sys.argv[2:]
manifest = json.loads((root / "manifest.json").read_text())
expected = {
    "component": "postgresql", "version": "18.6", "postgresql_version": "18.6",
    "platform": "macos", "architecture": architecture, "build_id": core_build_id,
    "source_revision": "748e1fb698ee8f87df4cf68d70670c6f8f3adde8",
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
curl -fL --retry 3 -o pg_cron.tar.gz "$source_url"
printf '%s  %s\n' "$source_sha256" pg_cron.tar.gz | shasum -a 256 -c -
test "$(tar -tzf pg_cron.tar.gz | cut -d/ -f1 | sort -u)" = pg_cron-1.6.8
tar -xzf pg_cron.tar.gz
cd pg_cron-1.6.8
test "$(sed -n "s/^default_version = '\\([^']*\\)'/\\1/p" pg_cron.control)" = 1.6
make PG_CONFIG="$pg_config" PG_LDFLAGS='-Wl,-rpath,@loader_path' -j "$(sysctl -n hw.ncpu)"
make PG_CONFIG="$pg_config" install DESTDIR="$work/stage"

staged_root="$work/stage$(cd "$pgroot" && pwd -P)"
mkdir -p "$work/package/pg_cron"/{lib,share/extension,LICENSES}
cp "$staged_root/lib/pg_cron.dylib" "$work/package/pg_cron/lib/"
cp "$staged_root/share/extension/"pg_cron* "$work/package/pg_cron/share/extension/"
cp LICENSE "$work/package/pg_cron/LICENSES/pg_cron.txt"
cat > "$work/package/pg_cron/LICENSES/pg_cron-inventory.json" <<EOF
{"schema_version":1,"components":[{"component":"pg_cron","version":"$extension_version","payload_paths":["lib/pg_cron.dylib","share/extension"],"license_file":"pg_cron.txt","license_source":"https://github.com/citusdata/pg_cron/blob/v1.6.8/LICENSE","source_url":"$source_url","source_sha256":"$source_sha256","redistribution_review":{"status":"resolved","basis":"The unmodified pg_cron 1.6.8 source archive includes the PostgreSQL License for this project. It permits binary redistribution with its copyright notice, permission paragraph and disclaimer retained; this archive includes the complete upstream LICENSE text.","source_obligation":"none"}}]}
EOF
cat > "$work/package/metadata.json" <<EOF
{"project":"pg_cron","version":"$extension_version","sql_names":["pg_cron"],"requires":[],"configuration_prerequisites":[{"type":"postgresql_setting","name":"shared_preload_libraries","value":"pg_cron"},{"type":"postgresql_setting","name":"cron.use_background_workers","value":"on"}],"runtime_prerequisites":[],"postgresql_version":"$pg_version","platform":"macos","architecture":"$architecture","source":{"url":"$source_url","sha256":"$source_sha256"},"core_archive":{"basename":"$core_name","sha256":"$core_sha256"}}
EOF
grep -Fq 'Permission to use, copy, modify, and distribute this software' LICENSE

tar -C "$work/package" -czf "$output/$extension_name" pg_cron metadata.json
(cd "$output" && shasum -a 256 "$extension_name" > "$extension_name.sha256" && shasum -a 256 -c "$extension_name.sha256")
python3 "$repo/tools/check_extension_redistribution.py" "$output/$extension_name"
tar -xzf "$output/$extension_name" -C "$work/extracted"
extroot="$work/extracted/pg_cron"
test -s "$extroot/lib/pg_cron.dylib"
test -s "$extroot/LICENSES/pg_cron.txt"
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
    echo "pg_cron payload collision: $relative" >&2
    exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv "$pgroot" "$work/moved/postgresql"
pgroot="$work/moved/postgresql"
python3 "$repo/scripts/macos/static_analysis.py" "$pgroot" "$architecture" \
  --archive "$core_archives/$core_name" --archive "$output/$extension_name" \
  --report "$output/static-analysis.json"
cp -a "$extroot/." "$pgroot/"
python3 - "$pgroot" "$architecture" "$core_archives/$core_name" "$output/$extension_name" <<'PY' | tee "$output/pg-cron-macho-inspection.json"
import hashlib
import json
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(sys.argv[1]).resolve()
architecture = sys.argv[2]
archives = [pathlib.Path(value) for value in sys.argv[3:]]
module = root / "lib/pg_cron.dylib"
postgres = root / "bin/postgres"

def run(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(f"command failed: {' '.join(args)}: {result.stderr}")
    return result.stdout

def rpaths(binary):
    lines = run("otool", "-l", str(binary)).splitlines()
    values = []
    for index, line in enumerate(lines):
        if line.strip() == "cmd LC_RPATH":
            match = re.search(r"^\s*path (.+?) \(offset ", lines[index + 2])
            if match:
                values.append(match.group(1))
    return values

if architecture not in run("lipo", "-archs", str(module)).split():
    raise SystemExit(f"pg_cron.dylib lacks the required {architecture} architecture")
load = run("otool", "-l", str(module))
minimum = re.search(r"\bminos (\d+(?:\.\d+){0,2})", load)
if not minimum or tuple(map(int, minimum.group(1).split(".")))[:2] > (11, 0):
    raise SystemExit("pg_cron.dylib lacks compatible minimum macOS metadata")
dependencies = [line.strip().split(" (compatibility version", 1)[0]
                for line in run("otool", "-L", str(module)).splitlines()[1:] if line.strip()]
executable_rpaths = rpaths(postgres)
module_rpaths = rpaths(module)
resolved = {}
findings = []
for dependency in dependencies:
    if dependency.startswith(("/usr/lib/", "/System/Library/")):
        resolved[dependency] = dependency
    elif dependency.startswith("@rpath/"):
        suffix = dependency.removeprefix("@rpath/")
        candidates = []
        for value in module_rpaths + executable_rpaths:
            if value.startswith("@loader_path"):
                base = module.parent / value.removeprefix("@loader_path").lstrip("/")
            elif value.startswith("@executable_path"):
                base = postgres.parent / value.removeprefix("@executable_path").lstrip("/")
            elif value.startswith("/"):
                base = pathlib.Path(value)
            else:
                continue
            candidate = (base / suffix).resolve()
            if candidate.is_file() and candidate.is_relative_to(root):
                candidates.append(candidate)
        if not candidates:
            findings.append({"error": "unresolved dependency", "path": dependency})
        else:
            resolved[dependency] = str(candidates[0].relative_to(root))
    else:
        findings.append({"error": "unsupported dependency token", "path": dependency})
report = {
    "architecture": architecture,
    "file": "lib/pg_cron.dylib",
    "minimum_os": minimum.group(1),
    "dependencies": resolved,
    "module_rpaths": module_rpaths,
    "postgres_executable_rpaths": executable_rpaths,
    "resolution_note": "@rpath dependencies use the dyld run-path stack, which includes run paths from the executable loading the extension.",
    "archives": {archive.name: hashlib.sha256(archive.read_bytes()).hexdigest()
                 for archive in archives},
    "findings": findings,
    "passed": not findings,
}
print(json.dumps(report, indent=2, sort_keys=True))
if findings:
    raise SystemExit("pg_cron Mach-O dependency inspection failed")
PY

data_dir="$work/data"
pg_ctl="$pgroot/bin/pg_ctl"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
printf 'installation_relocated=true\njob_execution_mode=background_worker\n' \
  | tee "$output/probe-output.txt"
"$pgroot/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >/dev/null
"$pg_ctl" -D "$data_dir" -l "$work/server.log" -o \
  "-k $work/socket -p 55432 -h '' -c shared_preload_libraries=pg_cron -c cron.use_background_workers=on -c max_worker_processes=20 -c cron.database_name=postgres" -w start
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 -d postgres <<'SQL' | tee -a "$output/probe-output.txt"
CREATE EXTENSION pg_cron;
CREATE TABLE public.pg_cron_probe (ran_at timestamptz NOT NULL);
SELECT cron.schedule('feasibility-probe', '* * * * *',
  'INSERT INTO public.pg_cron_probe VALUES (clock_timestamp())');
SQL
job_id=$("$pgroot/bin/psql" -X -At -h "$work/socket" -p 55432 -d postgres \
  -c "SELECT jobid FROM cron.job WHERE jobname = 'feasibility-probe'")
[[ $job_id =~ ^[0-9]+$ ]]
deadline=$((SECONDS + 150))
while (( SECONDS < deadline )); do
  status=$("$pgroot/bin/psql" -X -At -h "$work/socket" -p 55432 -d postgres \
    -c "SELECT status FROM cron.job_run_details WHERE jobid = $job_id ORDER BY runid DESC LIMIT 1")
  [[ "$status" == succeeded ]] && break
  sleep 2
done
if [[ ${status:-} != succeeded ]]; then
  cat "$work/server.log" >&2
  echo 'pg_cron did not complete the scheduled command before timeout' >&2
  exit 1
fi
rows=$("$pgroot/bin/psql" -X -At -h "$work/socket" -p 55432 -d postgres \
  -c 'SELECT count(*) FROM public.pg_cron_probe')
[[ $rows =~ ^[0-9]+$ ]] && (( rows > 0 ))
printf 'scheduled_job_status=%s\nscheduled_job_rows=%s\n' "$status" "$rows" \
  | tee -a "$output/probe-output.txt"
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 -d postgres \
  -c "DO \$\$ BEGIN IF (SELECT count(*) FROM public.pg_cron_probe) < 1 THEN RAISE EXCEPTION 'scheduled command did not insert a row'; END IF; END \$\$; SELECT cron.unschedule($job_id);" \
  | tee -a "$output/probe-output.txt"
"$pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=
pg_ctl=
echo "PASS: pg_cron $extension_version built from pinned unmodified source, relocated, inspected and exercised on macOS $architecture with PostgreSQL $pg_version"
