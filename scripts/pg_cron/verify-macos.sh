#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: verify-macos.sh CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY TARGET_JSON OUTPUT_DIRECTORY}
extension_archives=${2:?usage: verify-macos.sh CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY TARGET_JSON OUTPUT_DIRECTORY}
target_config=${3:?usage: verify-macos.sh CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY TARGET_JSON OUTPUT_DIRECTORY}
output=${4:?usage: verify-macos.sh CORE_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY TARGET_JSON OUTPUT_DIRECTORY}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
target_values=$(python3 "$repo/scripts/pg_cron/macos_target.py" --require-resolved "$target_config")
IFS=$'\t' read -r pg_version architecture platform core_name core_sha256 core_build_id \
  core_source_revision source_url source_sha256 extension_name <<< "$target_values"
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This verifier requires native macOS $architecture" >&2
  exit 1
fi
if [[ $(id -u) == 0 ]]; then echo 'Verification must run as an ordinary user' >&2; exit 1; fi
core_archives=$(cd "$core_archives" && pwd)
extension_archives=$(cd "$extension_archives" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
test -s "$core_archives/$core_name" && test -s "$core_archives/$core_name.sha256"
test -s "$extension_archives/$extension_name" && test -s "$extension_archives/$extension_name.sha256"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_archives" && shasum -a 256 -c -)
(cd "$extension_archives" && shasum -a 256 -c "$extension_name.sha256")
python3 "$repo/tools/check_extension_redistribution.py" "$extension_archives/$extension_name"

python3 - "$core_archives/$core_name" "$extension_archives/$extension_name" "$pg_version" "$architecture" "$platform" "$core_name" "$core_sha256" "$core_build_id" "$core_source_revision" "$source_url" "$source_sha256" <<'PY'
import json
import pathlib
import sys
import tarfile
core_path, ext_path, version, arch, platform, core_name, core_sha, build_id, revision, url, source_sha = sys.argv[1:]
with tarfile.open(core_path, "r:gz") as archive:
    member = archive.getmember("postgresql/manifest.json")
    if not member.isfile() or member.size > 1024 * 1024:
        raise SystemExit("core archive requires a bounded regular manifest")
    manifest = json.load(archive.extractfile(member))
with tarfile.open(ext_path, "r:gz") as archive:
    members = archive.getmembers()
    if len(members) > 100_000:
        raise SystemExit("pg_cron archive has too many entries")
    names = [item.name for item in members]
    if len(names) != len(set(names)):
        raise SystemExit("pg_cron archive contains duplicate paths")
    for item in members:
        path = pathlib.PurePosixPath(item.name)
        if (path.is_absolute() or ".." in path.parts or "\\" in item.name
                or item.name.split("/", 1)[0] not in {"pg_cron", "metadata.json"}
                or not (item.isfile() or item.isdir())):
            raise SystemExit("pg_cron archive contains an unsafe or unexpected entry")
    metadata_member = archive.getmember("metadata.json")
    if not metadata_member.isfile() or metadata_member.size > 1024 * 1024:
        raise SystemExit("pg_cron archive requires bounded metadata.json")
    metadata = json.load(archive.extractfile(metadata_member))
expected_manifest = {"component":"postgresql", "version":version, "postgresql_version":version,
                    "platform":"macos", "architecture":arch, "build_id":build_id,
                    "source_revision":revision}
expected_metadata = {"project":"pg_cron", "version":"1.6.8", "sql_names":["pg_cron"],
                     "requires": [],
                     "configuration_prerequisites":[
                         {"type":"postgresql_setting","name":"shared_preload_libraries","value":"pg_cron"},
                         {"type":"postgresql_setting","name":"cron.use_background_workers","value":"on"}],
                     "runtime_prerequisites": [],
                     "postgresql_version":version, "platform":"macos", "architecture":arch,
                     "source":{"url":url,"sha256":source_sha},
                     "core_archive":{"basename":core_name,"sha256":core_sha}}
if any(manifest.get(key) != value for key, value in expected_manifest.items()):
    raise SystemExit("core archive manifest differs from checked target identity")
if any(metadata.get(key) != value for key, value in expected_metadata.items()):
    raise SystemExit("pg_cron metadata differs from checked target identity")
required = {"pg_cron/lib/pg_cron.dylib", "pg_cron/LICENSES/pg_cron.txt",
            "pg_cron/share/extension/pg_cron.control",
            "pg_cron/share/extension/pg_cron--1.0.sql",
            "pg_cron/share/extension/pg_cron--1.5--1.6.sql"}
if not required.issubset(names):
    raise SystemExit("pg_cron archive lacks required payload")
PY

work=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/pgcron-macos-verify.XXXXXX")
data_dir=
pg_ctl=
cleanup() {
  if [[ -n "$pg_ctl" && -n "$data_dir" ]]; then "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true; fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/core" "$work/extension" "$work/moved" "$work/socket"
tar -xzf "$core_archives/$core_name" -C "$work/core"
tar -xzf "$extension_archives/$extension_name" -C "$work/extension"
pgroot="$work/core/postgresql"
extroot="$work/extension/pg_cron"
while IFS= read -r -d '' source; do
  relative=${source#"$extroot/"}
  destination="$pgroot/$relative"
  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
    echo "pg_cron payload collision: $relative" >&2; exit 1
  fi
done < <(find "$extroot" -mindepth 1 -print0)
mv "$pgroot" "$work/moved/postgresql"
pgroot="$work/moved/postgresql"
python3 "$repo/scripts/macos/static_analysis.py" "$pgroot" "$architecture" \
  --archive "$core_archives/$core_name" --archive "$extension_archives/$extension_name" \
  --report "$output/static-analysis.json"
cp -a "$extroot/." "$pgroot/"
python3 - "$pgroot" "$architecture" "$core_archives/$core_name" "$extension_archives/$extension_name" <<'PY' | tee "$output/pg-cron-macho-inspection.json"
import hashlib, json, pathlib, re, subprocess, sys
root = pathlib.Path(sys.argv[1]).resolve(); architecture = sys.argv[2]
archives = [pathlib.Path(value) for value in sys.argv[3:]]
module = root / "lib/pg_cron.dylib"; postgres = root / "bin/postgres"
def run(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode: raise SystemExit(f"command failed: {' '.join(args)}: {result.stderr}")
    return result.stdout
def rpaths(binary):
    lines = run("otool", "-l", str(binary)).splitlines(); values=[]
    for index, line in enumerate(lines):
        if line.strip() == "cmd LC_RPATH":
            match = re.search(r"^\s*path (.+?) \(offset ", lines[index + 2])
            if match: values.append(match.group(1))
    return values
if architecture not in run("lipo", "-archs", str(module)).split(): raise SystemExit("pg_cron.dylib lacks required architecture")
load = run("otool", "-l", str(module)); minimum = re.search(r"\bminos (\d+(?:\.\d+){0,2})", load)
if not minimum or tuple(map(int, minimum.group(1).split(".")))[:2] > (11, 0): raise SystemExit("pg_cron.dylib lacks compatible minimum macOS metadata")
deps = [line.strip().split(" (compatibility version",1)[0] for line in run("otool","-L",str(module)).splitlines()[1:] if line.strip()]
module_rpaths=rpaths(module); executable_rpaths=rpaths(postgres); resolved={}; findings=[]
for dependency in deps:
    if dependency.startswith(("/usr/lib/", "/System/Library/")): resolved[dependency]=dependency
    elif dependency.startswith("@rpath/"):
        suffix=dependency.removeprefix("@rpath/"); candidates=[]
        for value in module_rpaths+executable_rpaths:
            if value.startswith("@loader_path"): base=module.parent/value.removeprefix("@loader_path").lstrip("/")
            elif value.startswith("@executable_path"): base=postgres.parent/value.removeprefix("@executable_path").lstrip("/")
            elif value.startswith("/"): base=pathlib.Path(value)
            else: continue
            candidate=(base/suffix).resolve()
            if candidate.is_file() and candidate.is_relative_to(root): candidates.append(candidate)
        if candidates: resolved[dependency]=str(candidates[0].relative_to(root))
        else: findings.append({"error":"unresolved dependency","path":dependency})
    else: findings.append({"error":"unsupported dependency token","path":dependency})
report={"architecture":architecture,"file":"lib/pg_cron.dylib","minimum_os":minimum.group(1),"dependencies":resolved,
        "module_rpaths":module_rpaths,"postgres_executable_rpaths":executable_rpaths,
        "resolution_note":"@rpath dependencies use the dyld run-path stack, which includes run paths from the executable loading the extension.",
        "archives":{archive.name:hashlib.sha256(archive.read_bytes()).hexdigest() for archive in archives},
        "findings":findings,"passed":not findings}
print(json.dumps(report,indent=2,sort_keys=True))
if findings: raise SystemExit("pg_cron Mach-O dependency inspection failed")
PY

data_dir="$work/data"; pg_ctl="$pgroot/bin/pg_ctl"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
printf 'installation_relocated=true\njob_execution_mode=background_worker\n' | tee "$output/probe-output.txt"
"$pgroot/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >"$output/initdb.log" 2>&1
"$pg_ctl" -D "$data_dir" -l "$output/postgresql.log" -o "-k $work/socket -p 55432 -h '' -c shared_preload_libraries=pg_cron -c cron.use_background_workers=on -c max_worker_processes=20 -c cron.database_name=postgres" -w start
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 -d postgres <<'SQL' | tee -a "$output/probe-output.txt"
CREATE EXTENSION pg_cron;
CREATE TABLE public.pg_cron_probe (ran_at timestamptz NOT NULL);
SELECT cron.schedule('feasibility-probe', '* * * * *',
  'INSERT INTO public.pg_cron_probe VALUES (clock_timestamp())');
SQL
job_id=$("$pgroot/bin/psql" -X -At -h "$work/socket" -p 55432 -d postgres -c "SELECT jobid FROM cron.job WHERE jobname = 'feasibility-probe'")
[[ $job_id =~ ^[0-9]+$ ]]
deadline=$((SECONDS + 150))
while (( SECONDS < deadline )); do
  status=$("$pgroot/bin/psql" -X -At -h "$work/socket" -p 55432 -d postgres -c "SELECT status FROM cron.job_run_details WHERE jobid = $job_id ORDER BY runid DESC LIMIT 1")
  [[ "$status" == succeeded ]] && break
  sleep 2
done
if [[ ${status:-} != succeeded ]]; then cat "$output/postgresql.log" >&2; echo 'pg_cron scheduled command timed out' >&2; exit 1; fi
rows=$("$pgroot/bin/psql" -X -At -h "$work/socket" -p 55432 -d postgres -c 'SELECT count(*) FROM public.pg_cron_probe')
[[ $rows =~ ^[0-9]+$ ]] && (( rows > 0 ))
printf 'scheduled_job_status=%s\nscheduled_job_rows=%s\n' "$status" "$rows" | tee -a "$output/probe-output.txt"
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 -d postgres \
  -c "DO \$\$ BEGIN IF (SELECT count(*) FROM public.pg_cron_probe) < 1 THEN RAISE EXCEPTION 'scheduled command did not insert a row'; END IF; END \$\$; SELECT cron.unschedule($job_id);" \
  | tee -a "$output/probe-output.txt"
"$pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=; pg_ctl=
echo "PASS: relocated pg_cron 1.6.8 archive verified on fresh macOS $architecture runner with PostgreSQL $pg_version"
