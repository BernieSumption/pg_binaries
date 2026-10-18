#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
input=${1:?usage: verify.sh LINUX_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY}
extension=${2:?usage: verify.sh LINUX_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY}
architecture=${PG_ARCHITECTURE:-x86_64}
pg_version=${PG_VERSION:-18.6}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
input=$(cd "$input" && pwd)
extension=$(cd "$extension" && pwd)
mkdir -p "$extension/static-analysis"
docker build --platform "$docker_platform" -f "$repo/scripts/collection/verify.Dockerfile" -t pg-binaries-collection-verifier "$repo"
docker run --rm -e PG_ARCHITECTURE="$architecture" -e PG_VERSION="$pg_version" --platform "$docker_platform" \
  -v "$input:/input:ro" -v "$extension:/extension:ro" \
  -v "$extension/static-analysis:/analysis" pg-binaries-collection-verifier
