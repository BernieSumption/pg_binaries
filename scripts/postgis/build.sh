#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
input=${1:?usage: build.sh LINUX_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
output=${2:?usage: build.sh LINUX_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
input=$(cd "$input" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
docker build --platform linux/amd64 -f "$repo/scripts/postgis/Dockerfile" -t pg-binaries-postgis-pilot "$repo"
docker run --rm --platform linux/amd64 -v "$input:/input:ro" -v "$output:/out" pg-binaries-postgis-pilot
