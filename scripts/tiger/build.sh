#!/usr/bin/env bash
set -euo pipefail

core=${1:?usage: build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY [SOURCE_DIRECTORY]}
output=${2:?usage: build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY [SOURCE_DIRECTORY]}
source_dir=${3:-"$output/source"}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core=$(cd "$core" && pwd)
mkdir -p "$output" "$source_dir"
output=$(cd "$output" && pwd)
source_dir=$(cd "$source_dir" && pwd)
docker build --platform "$docker_platform" -f "$repo/scripts/postgis/Dockerfile" -t pg-binaries-postgis-pilot "$repo"
docker run --rm --platform "$docker_platform" -e PG_ARCHITECTURE="$architecture" \
  -e PG_VERSION="${PG_VERSION:-18.6}" \
  -v "$core:/core:ro" -v "$source_dir:/source:ro" -v "$output:/out" -v "$repo:/repo:ro" \
  --entrypoint bash pg-binaries-postgis-pilot /repo/scripts/tiger/build-in-container.sh
