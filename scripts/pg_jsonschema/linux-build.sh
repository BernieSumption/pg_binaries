#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
input=${1:?usage: linux-build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
output=${2:?usage: linux-build.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
architecture=${PG_ARCHITECTURE:-x86_64}
pg_version=${PG_VERSION:-18.6}
extension_version=${PG_JSONSCHEMA_VERSION:?selected extension version is required}
case "$architecture" in x86_64) docker_platform=linux/amd64 ;; arm64) docker_platform=linux/arm64 ;; *) echo "Unsupported architecture: $architecture" >&2; exit 2 ;; esac
input=$(cd "$input" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
docker build --platform "$docker_platform" -f "$repo/scripts/pg_jsonschema/linux-build.Dockerfile" \
  -t pg-binaries-pg-jsonschema-linux-probe "$repo"
docker run --rm --platform "$docker_platform" -e PG_ARCHITECTURE="$architecture" -e PG_VERSION="$pg_version" -e PG_JSONSCHEMA_VERSION="$extension_version" -v "$input:/input:ro" -v "$output:/out" \
  pg-binaries-pg-jsonschema-linux-probe
