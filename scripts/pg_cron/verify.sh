#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
input=${1:?usage: verify.sh LINUX_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY}
extension=${2:?usage: verify.sh LINUX_ARCHIVE_DIRECTORY EXTENSION_ARCHIVE_DIRECTORY}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
input=$(cd "$input" && pwd)
extension=$(cd "$extension" && pwd)
mkdir -p "$extension/static-analysis"
docker build --platform "$docker_platform" -f "$repo/scripts/pg_cron/verify.Dockerfile" -t pg-binaries-pgcron-verifier "$repo"
docker run --rm -e PG_ARCHITECTURE="$architecture" --platform "$docker_platform" \
  -v "$input:/input:ro" -v "$extension:/extension:ro" \
  -v "$extension/static-analysis:/analysis" pg-binaries-pgcron-verifier
