#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: verify-macos.sh CORE_ARCHIVE_DIRECTORY BOTH_COLLECTION_ARCHIVES RESOLVED_TARGET_JSON OUTPUT_DIRECTORY}
archives=${2:?usage: verify-macos.sh CORE_ARCHIVE_DIRECTORY BOTH_COLLECTION_ARCHIVES RESOLVED_TARGET_JSON OUTPUT_DIRECTORY}
target_json=${3:?usage: verify-macos.sh CORE_ARCHIVE_DIRECTORY BOTH_COLLECTION_ARCHIVES RESOLVED_TARGET_JSON OUTPUT_DIRECTORY}
output=${4:?usage: verify-macos.sh CORE_ARCHIVE_DIRECTORY BOTH_COLLECTION_ARCHIVES RESOLVED_TARGET_JSON OUTPUT_DIRECTORY}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core_archives=$(cd "$core_archives" && pwd)
archives=$(cd "$archives" && pwd)
target_json=$(cd "$(dirname "$target_json")" && pwd)/$(basename "$target_json")
mkdir -p "$output"
output=$(cd "$output" && pwd)

IFS=$'\t' read -r pg_version architecture core_name core_sha256 core_build_id core_source_revision source_1_1_1 source_2_1_3 <<< "$(PYTHONPATH="$repo/tools" python3 - "$target_json" <<'PY'
import sys
from collection_macos_target import load_target, VERSIONS
target = load_target(sys.argv[1], require_resolved=True)
print("\t".join((target.postgresql_version, target.architecture,
                 target.core_basename, target.core_sha256, target.core_build_id,
                 target.core_source_revision, VERSIONS["1.1.1"], VERSIONS["2.1.3"])))
PY
)"
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "Collection verification requires a fresh native macOS $architecture runner" >&2
  exit 1
fi
test -s "$core_archives/$core_name" && test -s "$core_archives/$core_name.sha256"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_archives" && shasum -a 256 -c -)

work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/collection-verify.XXXXXX")
pg_ctl=
data_dir=
cleanup() {
  if [[ -n $pg_ctl && -n $data_dir ]]; then "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true; fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/socket"
python3 - "$core_archives/$core_name" "$architecture" "$pg_version" "$core_build_id" "$core_source_revision" <<'PY'
import json, pathlib, re, sys, tarfile
archive = pathlib.Path(sys.argv[1])
architecture, version, build_id, revision = sys.argv[2:]
with tarfile.open(archive, "r:gz") as stream:
    members = stream.getmembers()
    if len(members) > 100000:
        raise SystemExit("core archive has too many entries")
    matches = [member for member in members if member.name == "postgresql/manifest.json"]
    if len(matches) != 1 or not matches[0].isfile() or matches[0].size > 1024 * 1024:
        raise SystemExit("core archive must contain one bounded manifest")
    manifest = json.load(stream.extractfile(matches[0]))
expected = {"component":"postgresql", "version":version, "postgresql_version":version,
            "platform":"macos", "architecture":architecture, "build_id":build_id,
            "source_revision":revision}
if any(manifest.get(key) != value for key, value in expected.items()):
    raise SystemExit("core manifest differs from resolved target identity")
PY

for version in 1.1.1 2.1.3; do
  archive="collection-${version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
  python3 "$repo/tools/license_pointer.py" verify "$archives/$archive" collection
  test -s "$archives/$archive" && test -s "$archives/$archive.sha256"
  (cd "$archives" && shasum -a 256 -c "$archive.sha256")
  python3 - "$archives/$archive" "$version" "$architecture" "$pg_version" "$core_name" "$core_sha256" <<'PY'
import json, pathlib, sys, tarfile
archive = pathlib.Path(sys.argv[1])
version, architecture, pg_version, core_name, core_sha256 = sys.argv[2:]
with tarfile.open(archive, "r:gz") as stream:
    names = set(stream.getnames())
    modules = names & {"collection/lib/collection.dylib", "collection/lib/collection.so"}
    expected_names = {"collection", "collection/lib", *modules, "collection/share",
        "collection/share/extension", *[name for name in names if name.startswith("collection/share/extension/")],
        "collection/LICENSES", "collection/LICENSES/collection",
        "collection/LICENSES/collection/LICENCE", "metadata.json"}
    if len(modules) != 1 or names != expected_names:
        raise SystemExit("collection archive has missing or unexpected members")
    metadata = json.load(stream.extractfile("metadata.json"))
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
  python3 "$repo/tools/check_extension_redistribution.py" "$archives/$archive"
done

for version in 1.1.1 2.1.3; do
  archive="collection-${version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
  mkdir -p "$work/verify-${version}"
  tar -xzf "$core_archives/$core_name" -C "$work/verify-${version}"
  pgroot="$work/verify-${version}/postgresql"
  test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
  rm -rf "$work/extracted" && mkdir -p "$work/extracted"
  tar -xzf "$archives/$archive" -C "$work/extracted"
  extroot="$work/extracted/collection"
  while IFS= read -r -d '' source; do
    relative=${source#"$extroot/"}
    destination="$pgroot/$relative"
    if [[ -e "$destination" || -L "$destination" ]]; then
      if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
      echo "collection $version payload collision: $relative" >&2
      exit 1
    fi
  done < <(find "$extroot" -mindepth 1 -print0)
  mkdir -p "$work/moved/$version"
  mv "$pgroot" "$work/moved/$version/postgresql"
  pgroot="$work/moved/$version/postgresql"
  cp -a "$extroot/." "$pgroot/"
  python3 "$repo/scripts/macos/static_analysis.py" "$pgroot" "$architecture" \
    --archive "$core_archives/$core_name" --archive "$archives/$archive" \
    --report "$output/static-analysis-collection-${version}.json"
  data_dir="$work/data-${version}"
  pg_ctl="$pgroot/bin/pg_ctl"
  export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
  "$pgroot/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions > "$work/initdb-${version}.log" 2>&1
  "$pg_ctl" -D "$data_dir" -l "$work/server-${version}.log" \
    -o "-k $work/socket -p 55432 -h ''" -w start
  "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 -d postgres \
    -f "$repo/scripts/collection/probe.sql" | tee "$output/probe-${version}.txt"
  "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 -d postgres <<'SQL'
DO $$
DECLARE c collection;
BEGIN
  SELECT value INTO c FROM public.collection_persist_probe;
  IF count(c) <> 2 OR find(c, 'alpha') <> 'one' THEN
    RAISE EXCEPTION 'collection persisted datum did not survive a new connection';
  END IF;
END;
$$;
DROP TABLE public.collection_persist_probe;
SQL
  if [[ $version == 2.1.3 ]]; then
    "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 -d postgres <<'SQL' | tee "$output/integer-collection-probe.txt"
DO $$
DECLARE
  i icollection('text');
  result text[];
  result_count integer;
BEGIN
  i[1] := 'first';
  i[1000000] := 'millionth';
  IF count(i) <> 2 OR NOT exist(i, 1) OR exist(i, 500)
     OR find(i, 1000000) <> 'millionth' THEN
    RAISE EXCEPTION 'integer-key collection sparse lookup/count failed';
  END IF;
  SELECT count(*) INTO result_count FROM to_table(i) AS item(key, value);
  IF result_count <> 2 OR value_type(i) <> 'text'::regtype THEN
    RAISE EXCEPTION 'integer-key collection table or type metadata failed';
  END IF;
  CREATE TABLE public.collection_integer_probe (value icollection('text') NOT NULL);
  INSERT INTO public.collection_integer_probe VALUES (i);
  i := NULL;
  i[4] := 'four';
  result := to_array(i, NULL::text);
  IF result IS NULL OR result[4] <> 'four' THEN
    RAISE EXCEPTION 'typed NULL to_array carrier failed';
  END IF;
END;
$$;
DO $$
DECLARE i icollection('text');
BEGIN
  SELECT value INTO i FROM public.collection_integer_probe;
  IF count(i) <> 2 OR find(i, 1000000) <> 'millionth' THEN
    RAISE EXCEPTION 'integer-key collection persisted datum failed';
  END IF;
END;
$$;
DROP TABLE public.collection_integer_probe;
SELECT 'integer collection probe passed' AS outcome;
SQL
  fi
  "$pg_ctl" -D "$data_dir" -m fast -w stop
  pg_ctl=
  data_dir=
done

python3 - "$core_archives/$core_name" "$archives" "$output" "$architecture" "$pg_version" "$core_sha256" <<'PY'
import hashlib, json, pathlib, sys
core, archive_dir, report_dir, architecture, pg_version, core_sha = sys.argv[1:]
core = pathlib.Path(core)
archive_dir, report_dir = pathlib.Path(archive_dir), pathlib.Path(report_dir)
expected_core = {pathlib.Path(core).name: core_sha}
if hashlib.sha256(pathlib.Path(core).read_bytes()).hexdigest() != core_sha:
    raise SystemExit("resolved core archive bytes changed during verification")
for version in ("1.1.1", "2.1.3"):
    name = f"collection-{version}-postgresql-{pg_version}-macos-{architecture}.tar.gz"
    extension_sha = hashlib.sha256((archive_dir / name).read_bytes()).hexdigest()
    expected = {**expected_core, name: extension_sha}
    report_path = report_dir / f"static-analysis-collection-{version}.json"
    report = json.loads(report_path.read_text())
    actual = report.get("archives")
    if isinstance(actual, list):
        actual = {item["basename"]: item["sha256"] for item in actual}
    module = "lib/collection.dylib"
    if not any(item.get("file") == module for item in report.get("inspected_files", []) if isinstance(item, dict)):
        module = "lib/collection.so"
    if (report.get("passed") is not True or report.get("architecture") != architecture
            or actual != expected
            or not any(item.get("file") == module for item in report.get("inspected_files", []) if isinstance(item, dict))):
        raise SystemExit(f"static/Mach-O report for collection {version} does not bind the final archives")
PY
echo "PASS: both collection releases relocated, statically analysed, and exercised on PostgreSQL $pg_version/macOS $architecture"
