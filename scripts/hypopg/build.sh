#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
input=${1:?usage: build.sh LINUX_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
output=${2:?usage: build.sh LINUX_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
input=$(cd "$input" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
docker build --platform "$docker_platform" -f "$repo/scripts/hypopg/Dockerfile" -t pg-binaries-hypopg-pilot "$repo"
docker run --rm -e PG_ARCHITECTURE="$architecture" -e PG_VERSION="${PG_VERSION:-18.6}" --platform "$docker_platform" -v "$input:/input:ro" -v "$output:/out" pg-binaries-hypopg-pilot
