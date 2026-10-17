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
build_version=${PG_VERSION:-18.6}
range_from=${POSTGIS_PG_RANGE_FROM:-}
if [[ ! $build_version =~ ^([0-9]+)\.([0-9]+)$ ]]; then
  echo "Unsupported PostgreSQL version format: $build_version" >&2
  exit 2
fi
build_major=${BASH_REMATCH[1]}
build_minor=${BASH_REMATCH[2]}
if [[ -n $range_from ]]; then
  if [[ ! $range_from =~ ^([0-9]+)\.([0-9]+)$ ]]; then
    echo "Unsupported PostGIS PostgreSQL range start: $range_from" >&2
    exit 2
  fi
  range_major=${BASH_REMATCH[1]}
  range_minor=${BASH_REMATCH[2]}
  if (( 10#$range_major != 10#$build_major || 10#$range_minor > 10#$build_minor )); then
    echo "PostGIS range start must use the build major and be no newer than $build_version" >&2
    exit 2
  fi
fi
docker build --platform "$docker_platform" -f "$repo/scripts/postgis/Dockerfile" -t pg-binaries-postgis-pilot "$repo"
docker run --rm -e PG_ARCHITECTURE="$architecture" -e PG_VERSION="$build_version" -e POSTGIS_PG_RANGE_FROM="$range_from" --platform "$docker_platform" -v "$input:/input:ro" -v "$output:/out" pg-binaries-postgis-pilot
