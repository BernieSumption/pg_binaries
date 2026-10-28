#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 3 ]]; then
  echo "usage: $0 POSTGRESQL_DEVELOPMENT_ARCHIVE OUTPUT_DIR WORK_DIR" >&2
  exit 2
fi
pg_archive=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
output_dir=$2
work_dir=$3
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
mkdir -p "$output_dir" "$work_dir"
output_dir=$(cd "$output_dir" && pwd)
work_dir=$(cd "$work_dir" && pwd)
[[ -f $pg_archive ]] || { echo "Missing PostgreSQL development archive: $pg_archive" >&2; exit 1; }
[[ $(uname -m) == arm64 ]] || { echo 'Run this build on an ARM64 host' >&2; exit 1; }

read_source() {
  python3 - "$repo_root/support.json" "$1" "$2" <<'PY'
import json, sys
entry = json.load(open(sys.argv[1]))['packages']['postgis']['sources']
source = next(item for item in entry if item['project'] == sys.argv[2])
print(source[sys.argv[3]])
PY
}
postgis_url=$(read_source 'PostGIS' url)
postgis_sha=$(read_source 'PostGIS' sha256)
tiger_url=$(read_source 'PostGIS TIGER Geocoder' url)
tiger_sha=$(read_source 'PostGIS TIGER Geocoder' sha256)
pg_version=$(python3 -c 'import json; print(json.load(open("'"$repo_root"'/support.json"))["postgresql"]["version"])')
archive="postgis-postgresql-${pg_version}-linux-arm64.tar.gz"

docker build --platform linux/arm64 -t pg-binaries-postgis-linux-arm64 "$repo_root/packages/postgis/linux-arm64"
docker run --rm --platform linux/arm64 \
  -v "$pg_archive:/input/postgresql-development.tar.gz:ro" \
  -v "$repo_root/support.json:/input/support.json:ro" \
  -v "$output_dir:/out" -v "$work_dir:/work" \
  -e POSTGRESQL_VERSION="$pg_version" \
  -e POSTGIS_URL="$postgis_url" -e POSTGIS_SHA256="$postgis_sha" \
  -e TIGER_URL="$tiger_url" -e TIGER_SHA256="$tiger_sha" \
  pg-binaries-postgis-linux-arm64
printf '%s\n' "$output_dir/$archive"
