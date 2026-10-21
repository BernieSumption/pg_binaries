#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY PG_VERSION ARCHITECTURE}
output=${2:?usage: macos-build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY PG_VERSION ARCHITECTURE}
pg_version=${3:?usage: macos-build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY PG_VERSION ARCHITECTURE}
architecture=${4:?usage: macos-build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY PG_VERSION ARCHITECTURE}
case "$pg_version" in 16.*|17.*|18.*) ;; *) echo "Unsupported PostgreSQL version: $pg_version" >&2; exit 2 ;; esac
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported macOS architecture: $architecture" >&2; exit 2 ;; esac
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "TIGER build requires native macOS $architecture" >&2
  exit 1
fi
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core_archives=$(cd "$core_archives" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
core_name="postgresql-${pg_version}-macos-${architecture}.tar.gz"
archive="postgis_tiger_geocoder-2025.2-postgresql-${pg_version}-macos-${architecture}.tar.gz"
test -s "$core_archives/$core_name" && test -s "$core_archives/$core_name.sha256"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")

work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/tiger-macos-build.XXXXXX")
prefix_link_created=false
prefix_link=
cleanup() {
  source "$repo/scripts/macos/core-prefix.sh"
  macos_remove_core_prefix
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/core" "$work/source" "$work/package/postgis_tiger_geocoder/share/extension"
tar -xzf "$core_archives/$core_name" -C "$work/core"
pgroot="$work/core/postgresql"
manifest=$(python3 - "$pgroot/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1])); print('\t'.join((m['build_id'],m['source_revision'])))
PY
)
IFS=$'\t' read -r core_build_id core_revision <<< "$manifest"
source "$repo/scripts/macos/core-prefix.sh"
prefix=$(macos_core_prefix_from_archive "$pgroot" "$pg_version" "$architecture" "$core_build_id" "$core_revision")
macos_restore_core_prefix "$prefix" "$pgroot"
pg_config="$prefix/bin/pg_config"
test "$("$pg_config" --version)" = "PostgreSQL $pg_version"

cd "$work/source"
make --version | grep 'GNU Make' >/dev/null
source_name=postgis_tiger_geocoder-2025.2.tar.gz
source_url="https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/$source_name"
source_sha256=c33cfbfb40785db8754a36be66060e8d023773e7e1be8fb8a622bb3c48db9f54
curl -fL --retry 3 -o "$source_name" "$source_url"
printf '%s  %s\n' "$source_sha256" "$source_name" | shasum -a 256 -c -
tar -xzf "$source_name"
cd postgis_tiger_geocoder
make PG_CONFIG="$pg_config" all
payload="$work/package/postgis_tiger_geocoder"
cp postgis_tiger_geocoder.control "$payload/share/extension/"
find data -maxdepth 1 -type f -name 'postgis_tiger_geocoder*.sql' -exec cp {} "$payload/share/extension/" \;
test -s "$payload/share/extension/postgis_tiger_geocoder--2025.2.sql"
python3 "$repo/tools/license_pointer.py" write "$payload" postgis_tiger_geocoder
python3 - "$work/package/metadata.json" "$pg_version" "$architecture" "$source_url" "$source_sha256" <<'PY'
import json, pathlib, sys
path, version, architecture, url, source_sha = sys.argv[1:]
metadata = {
    'project':'postgis_tiger_geocoder', 'version':'2025.2',
    'sql_names':['postgis_tiger_geocoder'], 'requires':['PostGIS'],
    'configuration_prerequisites':[{'type':'postgresql_setting','name':'search_path','value':'"$user",public,tiger'},
        {'type':'sql_extension','name':'fuzzystrmatch','value':'CREATE EXTENSION fuzzystrmatch'}],
    'runtime_prerequisites':[], 'postgresql_version':version, 'platform':'macos',
    'architecture':architecture, 'source':{'url':url,'sha256':source_sha}}
pathlib.Path(path).write_text(json.dumps(metadata,indent=2,sort_keys=True)+'\n')
PY
tar -C "$work/package" -czf "$output/$archive" postgis_tiger_geocoder metadata.json
python3 "$repo/tools/license_pointer.py" verify "$output/$archive" postgis_tiger_geocoder
(cd "$output" && shasum -a 256 "$archive" > "$archive.sha256")
echo "PASS: packaged TIGER Geocoder 2025.2 for PostgreSQL $pg_version macOS $architecture"
