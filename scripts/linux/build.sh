#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
out=${1:?usage: build.sh OUTPUT_DIRECTORY}
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
if [[ ! $pg_version =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Linux pilot currently supports PostgreSQL 15 through 18 minors only: $pg_version" >&2
  exit 2
fi
python3 "$repo/tools/plan_work.py" --select-linux-pilot "$pg_version" --architecture "$architecture" >/dev/null
mkdir -p "$out"
out=$(cd "$out" && pwd)
docker build --platform "$docker_platform" -f "$repo/scripts/linux/Dockerfile" -t pg-binaries-linux-pilot "$repo"
docker run --rm --platform "$docker_platform" -e PG_VERSION="$pg_version" -e PG_ARCHITECTURE="$architecture" -v "$out:/out" pg-binaries-linux-pilot
