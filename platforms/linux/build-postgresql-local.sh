#!/usr/bin/env bash
set -euo pipefail

[[ $# == 1 ]] || { echo "usage: $0 OUTPUT_DIR" >&2; exit 2; }
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
mkdir -p "$1"
output_dir=$(cd "$1" && pwd)
version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["postgresql"]["version"])' "$repo/support.json")
container=$(bash "$repo/platforms/linux/dev-container.sh")
docker exec "$container" mkdir -p /work/output
docker exec "$container" rm -rf /opt/postgresql
for archive in "postgresql-$version-linux-arm64.tar.gz" "postgresql-development-$version-linux-arm64.tar.gz"; do
  docker exec "$container" rm -f "/work/output/$archive" "/work/output/$archive.sha256"
done
docker exec "$container" bash -c '
  set -euo pipefail
  python3 build.py --target linux-arm64 postgresql-build /work/dependencies /work/build /opt/postgresql
  python3 build.py --target linux-arm64 postgresql-package /opt/postgresql /work/dependencies /work/output
'
for archive in "postgresql-$version-linux-arm64.tar.gz" "postgresql-development-$version-linux-arm64.tar.gz"; do
  docker cp "$container:/work/output/$archive" "$output_dir/$archive"
  docker cp "$container:/work/output/$archive.sha256" "$output_dir/$archive.sha256"
done
