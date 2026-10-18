#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core=${1:?usage: linux-build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
output=${2:?usage: linux-build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
architecture=${PG_ARCHITECTURE:-x86_64}
pg_version=${PG_VERSION:-18.6}
[[ $architecture == x86_64 ]] || { echo "Unsupported architecture: $architecture" >&2; exit 2; }
[[ $pg_version == 18.6 ]] || { echo "Unsupported PostgreSQL version: $pg_version" >&2; exit 2; }
core=$(cd "$core" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
docker build --platform linux/amd64 -f "$repo/scripts/pg_stat_monitor/linux-build.Dockerfile" \
  -t pg-binaries-pg-stat-monitor-builder "$repo"
docker run --rm --platform linux/amd64 -e PG_ARCHITECTURE="$architecture" -e PG_VERSION="$pg_version" \
  -v "$core:/input:ro" -v "$output:/out" pg-binaries-pg-stat-monitor-builder
