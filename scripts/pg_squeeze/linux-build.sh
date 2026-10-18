#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
input=${1:?usage: linux-build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
output=${2:?usage: linux-build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
input=$(cd "$input" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
docker build --platform linux/amd64 -f "$repo/scripts/pg_squeeze/linux-build.Dockerfile" -t pg-binaries-pg-squeeze-linux-probe "$repo"
docker run --rm --platform linux/amd64 -e PG_VERSION=18.6 -e PG_ARCHITECTURE=x86_64 -v "$input:/input:ro" -v "$output:/out" pg-binaries-pg-squeeze-linux-probe
