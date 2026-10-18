#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY [arm64|x86_64]}
output=${2:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY [arm64|x86_64]}
architecture=${3:-arm64}
pg_version=18.6
case "$architecture" in
  arm64) core_sha256=bc543b0d54a8a33b3b737eab74d7f185035f01e5c2db4eb48be049996eee4440; core_build_id=github-39079982683-1 ;;
  x86_64) core_sha256=5ec45e48bad1439860f0143fd6f2cbc04a86cfa456beef8c5ca9040960ea3f40; core_build_id=github-39079982747-1 ;;
  *) echo "Unsupported macOS architecture: $architecture" >&2; exit 2 ;;
esac
core_name="postgresql-${pg_version}-macos-${architecture}.tar.gz"
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

work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/collection-macos.XXXXXX")
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
mkdir -p "$work/first" "$work/source" "$work/stage" "$work/extracted" "$work/moved" "$work/socket"
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
architecture, build_id = sys.argv[2:]
manifest = json.loads((root / "manifest.json").read_text())
expected = {
    "component": "postgresql", "version": "18.6", "postgresql_version": "18.6",
    "platform": "macos", "architecture": architecture, "build_id": build_id,
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

build_one() {
  local version=$1 source_sha256=$2
  local source_url="https://github.com/aws/pgcollection/archive/refs/tags/v${version}.tar.gz"
  local source_archive="pgcollection-v${version}.tar.gz"
  local source_dir="$work/source/${version}"
  local package="$work/package/${version}"
  local archive="collection-${version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
  mkdir -p "$source_dir" "$package/collection/lib" "$package/collection/share/extension" "$package/collection/LICENSES"
  curl -fL --retry 3 -o "$work/source/$source_archive" "$source_url"
  printf '%s  %s\n' "$source_sha256" "$work/source/$source_archive" | shasum -a 256 -c -
  test "$(tar -tzf "$work/source/$source_archive" | cut -d/ -f1 | sort -u)" = "pgcollection-${version}"
  tar -xzf "$work/source/$source_archive" -C "$source_dir"
  local source_root="$source_dir/pgcollection-${version}"
  test -f "$source_root/Makefile"
  test -f "$source_root/LICENSE"
  test -f "$source_root/collection.control.in" || test -f "$source_root/collection.control"
  test "$(sed -n 's/^EXTVERSION = //p' "$source_root/Makefile")" = "$version"
  make -C "$source_root" PG_CONFIG="$pg_config" PG_LDFLAGS='-Wl,-rpath,@loader_path' -j "$(sysctl -n hw.ncpu)"
  make -C "$source_root" PG_CONFIG="$pg_config" install DESTDIR="$work/stage/${version}"

  local staged_root="$work/stage/${version}$(cd "$pgroot" && pwd -P)"
  test -s "$staged_root/lib/collection.dylib"
  cp "$staged_root/lib/collection.dylib" "$package/collection/lib/"
  cp "$staged_root/share/extension/collection"* "$package/collection/share/extension/"
  cp "$source_root/LICENSE" "$package/collection/LICENSES/pgcollection.txt"
  cp "$source_root/NOTICE" "$package/collection/LICENSES/pgcollection-NOTICE.txt"
  test -f "$source_root/include/uthash/LICENSE"
  cp "$source_root/include/uthash/LICENSE" "$package/collection/LICENSES/uthash.txt"
  local uthash_sha
  uthash_sha=$(shasum -a 256 "$source_root/include/uthash/LICENSE" | awk '{print $1}')
  python3 - "$package" "$version" "$pg_version" "$architecture" "$source_url" "$source_sha256" "$uthash_sha" "$core_name" "$core_sha256" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
version, pg_version, architecture, url, sha256, uthash_sha, core_name, core_sha256 = sys.argv[2:]
metadata = {
    "project": "collection", "version": version, "sql_names": ["collection"],
    "requires": [], "configuration_prerequisites": [], "runtime_prerequisites": [],
    "postgresql_version": pg_version, "platform": "macos", "architecture": architecture,
    "source": {"url": url, "sha256": sha256},
    "core_archive": {"basename": core_name, "sha256": core_sha256},
}
(root / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
components = [{
    "component": "pgcollection", "version": version,
    "payload_paths": ["lib/collection.dylib", "share/extension"],
    "license_file": "pgcollection.txt", "additional_license_files": ["pgcollection-NOTICE.txt"],
    "license_source": url + "#LICENSE", "source_url": url, "source_sha256": sha256,
    "redistribution_review": {
        "status": "resolved",
        "basis": "The exact unmodified upstream source archive supplies the Apache-2.0 project license and NOTICE, retained in this archive.",
        "source_obligation": "none",
    },
}, {
    "component": "uthash", "version": "vendored by pgcollection",
    "payload_paths": ["lib/collection.dylib"], "license_file": "uthash.txt",
    "license_source": url + "#include/uthash/LICENSE", "source_url": url,
    "source_sha256": sha256, "license_sha256": uthash_sha,
    "redistribution_review": {
        "status": "resolved",
        "basis": "The unmodified upstream archive identifies and supplies the uthash license; its copyright, conditions and disclaimer are retained in this archive.",
        "source_obligation": "none",
    },
}]
(root / "collection/LICENSES/collection-inventory.json").write_text(
    json.dumps({"schema_version": 1, "components": components}, indent=2, sort_keys=True) + "\n")
PY
  tar -C "$package" -czf "$output/$archive" collection metadata.json
  (cd "$output" && shasum -a 256 "$archive" > "$archive.sha256" && shasum -a 256 -c "$archive.sha256")
}

build_one 1.1.1 ab99a969334442e4a3c77405bc9ffed0083595d18f3898d64a731353a32bec5e
build_one 2.1.3 a6b07864e5893d3b682bb3223fd6d33015709765c9d40d415c85112358f0e3e4

for version in 1.1.1 2.1.3; do
  archive="collection-${version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
  python3 - "$output/$archive" "$version" "$architecture" "$pg_version" "$core_name" "$core_sha256" <<'PY'
import json, pathlib, sys, tarfile
archive = pathlib.Path(sys.argv[1])
version, architecture, pg_version, core_name, core_sha256 = sys.argv[2:]
with tarfile.open(archive, "r:gz") as tar:
    names = set(tar.getnames())
    if names != {"collection", "collection/lib", "collection/lib/collection.dylib",
                 "collection/share", "collection/share/extension",
                 *[n for n in names if n.startswith("collection/share/extension/")],
                 "collection/LICENSES", "collection/LICENSES/pgcollection.txt",
                 "collection/LICENSES/pgcollection-NOTICE.txt", "collection/LICENSES/uthash.txt",
                 "collection/LICENSES/collection-inventory.json", "metadata.json"}:
        raise SystemExit("collection archive has missing or unexpected members")
    metadata = json.load(tar.extractfile("metadata.json"))
    expected = {
        "project": "collection", "version": version, "sql_names": ["collection"],
        "requires": [], "configuration_prerequisites": [], "runtime_prerequisites": [],
        "postgresql_version": pg_version, "platform": "macos", "architecture": architecture,
        "source": {"url": f"https://github.com/aws/pgcollection/archive/refs/tags/v{version}.tar.gz",
                   "sha256": {"1.1.1": "ab99a969334442e4a3c77405bc9ffed0083595d18f3898d64a731353a32bec5e",
                              "2.1.3": "a6b07864e5893d3b682bb3223fd6d33015709765c9d40d415c85112358f0e3e4"}[version]},
        "core_archive": {"basename": core_name, "sha256": core_sha256},
    }
    if metadata != expected:
        raise SystemExit("collection archive metadata identity mismatch")
PY
done

for version in 1.1.1 2.1.3; do
  python3 "$repo/tools/check_extension_redistribution.py" \
    "$output/collection-${version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
done

for version in 1.1.1 2.1.3; do
  archive="collection-${version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
  mkdir -p "$work/verify-${version}"
  tar -xzf "$core_archives/$core_name" -C "$work/verify-${version}"
  pgroot="$work/verify-${version}/postgresql"
  test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
  rm -rf "$work/extracted" && mkdir -p "$work/extracted"
  tar -xzf "$output/$archive" -C "$work/extracted"
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
    --archive "$core_archives/$core_name" --archive "$output/$archive" \
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

echo "PASS: collection 1.1.1 and 2.1.3 built from pinned upstream sources, relocated, statically analysed, and exercised with PostgreSQL $pg_version on macOS $architecture"
