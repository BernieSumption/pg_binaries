#!/usr/bin/env bash
set -euo pipefail
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture:$(uname -m)" in
  x86_64:x86_64|arm64:aarch64) ;;
  *) echo "Verifier architecture does not match $architecture: $(uname -m)" >&2; exit 2 ;;
esac
pg_version=${PG_VERSION:-18.6}
source /usr/local/bin/collection-version-selection.sh
select_collection_versions
case "$pg_version" in
  15.19|16.15|17.11|18.6) ;;
  *) echo "Unsupported PostgreSQL version: $pg_version" >&2; exit 2 ;;
esac
core_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$core_archive.sha256"
cd /extension
for version in "${SELECTED_COLLECTION_VERSIONS[@]}"; do
  archive="collection-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
  sha256sum -c "$archive.sha256"
done
useradd -m postgres
for version in "${SELECTED_COLLECTION_VERSIONS[@]}"; do
  archive="collection-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
  work="/tmp/collection-${version}"
  mkdir -p "$work/first" "$work/moved" "$work/package" "$work/data" "$work/socket"
  tar -xzf "/input/$core_archive" -C "$work/first"
  tar -xzf "/extension/$archive" -C "$work/package"
  pgroot="$work/first/postgresql"
  extroot="$work/package/collection"
  test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"
  python3 - "$work/package" "$version" "$architecture" "$pg_version" <<'PY'
import json, sys
import re
from pathlib import Path
root = Path(sys.argv[1])
version, architecture, pg_version = sys.argv[2:]
pins = {
    "1.1.1": "ab99a969334442e4a3c77405bc9ffed0083595d18f3898d64a731353a32bec5e",
    "2.1.3": "a6b07864e5893d3b682bb3223fd6d33015709765c9d40d415c85112358f0e3e4",
}
expected_source = {
    "url": f"https://github.com/aws/pgcollection/archive/refs/tags/v{version}.tar.gz",
    "sha256": pins[version],
}
metadata = json.loads((root / "metadata.json").read_text())
expected = {
    "project": "collection", "version": version, "sql_names": ["collection"],
    "requires": [], "configuration_prerequisites": [], "runtime_prerequisites": [],
    "postgresql_version": pg_version, "platform": "linux", "architecture": architecture,
}
for key, value in expected.items():
    if metadata.get(key) != value:
        raise SystemExit(f"metadata mismatch for {key}: {metadata.get(key)!r}")
if metadata.get("source") != expected_source:
    raise SystemExit("source identity mismatch in package metadata")
inv = json.loads((root / "collection/LICENSES/collection-inventory.json").read_text())
if inv.get("schema_version") != 1 or not inv.get("components"):
    raise SystemExit("missing license inventory")
components = {item.get("component"): item for item in inv["components"]}
if set(components) != {"pgcollection", "uthash"}:
    raise SystemExit("source component inventory mismatch")
if components["pgcollection"].get("source_sha256") != expected_source["sha256"]:
    raise SystemExit("project source checksum mismatch in license inventory")
if components["uthash"].get("license_sha256") != __import__("hashlib").sha256(
    (root / "collection/LICENSES/uthash.txt").read_bytes()
).hexdigest():
    raise SystemExit("uthash license checksum mismatch")
if not (root / "collection/LICENSES/pgcollection.txt").is_file():
    raise SystemExit("missing upstream project license")
if not (root / "collection/LICENSES/pgcollection-NOTICE.txt").is_file():
    raise SystemExit("missing upstream NOTICE")
if not (root / "collection/LICENSES/uthash.txt").is_file():
    raise SystemExit("missing uthash license")
if {path.name for path in root.iterdir()} != {"collection", "metadata.json"}:
    raise SystemExit("unexpected collection archive members")
controls = list((root / "collection/share/extension").glob("collection.control"))
if len(controls) != 1 or not (root / "collection/lib/collection.so").is_file():
    raise SystemExit("collection payload is incomplete")
control = controls[0].read_text()
match = re.search(r"^default_version\s*=\s*'([^']+)'", control, re.M)
if not match or match.group(1) != version:
    raise SystemExit("installed extension control version mismatch")
PY
  while IFS= read -r -d '' source; do
    relative=${source#"$extroot/"}
    destination="$pgroot/$relative"
    if [[ -e "$destination" || -L "$destination" ]]; then
      if [[ -d "$source" && ! -L "$source" && -d "$destination" && ! -L "$destination" ]]; then continue; fi
      echo "collection $version payload collision: $relative" >&2
      exit 1
    fi
  done < <(find "$extroot" -mindepth 1 -print0)
  mv "$pgroot" "$work/moved/postgresql"
  pgroot="$work/moved/postgresql"
  cp -a "$extroot/." "$pgroot/"
  python3 /usr/local/bin/check-elf-dependencies "$pgroot" --architecture "$architecture" \
    --archive "/input/$core_archive" --archive "/extension/$archive" \
    --report "/analysis/collection-${version}.json"
  chown postgres:postgres "$work/data" "$work/socket"
  runuser -u postgres -- "$pgroot/bin/initdb" -D "$work/data" --encoding=UTF8 --locale=C --no-instructions
  runuser -u postgres -- "$pgroot/bin/pg_ctl" -D "$work/data" -l "$work/data/server.log" \
    -o "-k $work/socket -p 55433 -h ''" -w start
  trap 'runuser -u postgres -- "$pgroot/bin/pg_ctl" -D "$work/data" -m immediate stop >/dev/null 2>&1 || true' EXIT
  runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 \
    -h "$work/socket" -p 55433 -d postgres -f /usr/local/share/collection-probe.sql
  runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 \
    -h "$work/socket" -p 55433 -d postgres <<'SQL'
DO $$
DECLARE
    c collection;
BEGIN
    SELECT value INTO c FROM public.collection_persist_probe;
    IF count(c) <> 2 OR find(c, 'alpha') <> 'one' THEN
        RAISE EXCEPTION 'collection persisted datum did not survive a new connection';
    END IF;
END;
$$;
DROP TABLE public.collection_persist_probe;
SQL
  if [[ $version = 2.1.3 ]]; then
    runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 \
      -h "$work/socket" -p 55433 -d postgres <<'SQL'
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
SQL
    runuser -u postgres -- "$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 \
      -h "$work/socket" -p 55433 -d postgres <<'SQL'
DO $$
DECLARE
    i icollection('text');
BEGIN
    SELECT value INTO i FROM public.collection_integer_probe;
    IF count(i) <> 2 OR find(i, 1000000) <> 'millionth' THEN
        RAISE EXCEPTION 'integer-key collection persisted datum failed';
    END IF;
END;
$$;
DROP TABLE public.collection_integer_probe;
SQL
  fi
  runuser -u postgres -- "$pgroot/bin/pg_ctl" -D "$work/data" -m fast -w stop
  trap - EXIT
  echo "PASS: collection $version on relocated PostgreSQL $pg_version in Alpine 3.22 ($architecture)"
done
