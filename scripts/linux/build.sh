#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
out=${1:?usage: build.sh OUTPUT_DIRECTORY}
pg_version=${PG_VERSION:-18.6}
if [[ ! $pg_version =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Linux pilot currently supports PostgreSQL 15 through 18 minors only: $pg_version" >&2
  exit 2
fi
python3 "$repo/tools/plan_work.py" --select-linux-pilot "$pg_version" >/dev/null
mkdir -p "$out"
out=$(cd "$out" && pwd)
docker build --platform linux/amd64 -f "$repo/scripts/linux/Dockerfile" -t pg-binaries-linux-pilot "$repo"
docker run --rm --platform linux/amd64 -e PG_VERSION="$pg_version" -v "$out:/out" pg-binaries-linux-pilot
