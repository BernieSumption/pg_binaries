#!/usr/bin/env bash
set -euo pipefail

[[ $# == 1 ]] || { echo "usage: $0 OUTPUT_DIR" >&2; exit 2; }
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
mkdir -p "$1"
output_dir=$(cd "$1" && pwd)
container=$(bash "$repo/platforms/linux/dev-container.sh")
job=$(docker exec "$container" mktemp -d /work/postgresql.XXXXXX)
docker exec "$container" bash -c '
  set -euo pipefail
  python3 build.py --target linux-arm64 prepare-dependencies postgresql
  python3 build.py --target linux-arm64 postgresql-build "$1/workspace" --source-cache /work/source-cache
  python3 build.py --target linux-arm64 postgresql-package "$1/workspace" "$1/output"
' _ "$job"
docker cp "$container:$job/output/." "$output_dir/"
