#!/usr/bin/env bash
set -euo pipefail

core=${1:?usage: verify.sh CORE_ARCHIVE_DIRECTORY POSTGIS_ARCHIVE_DIRECTORY TIGER_ARCHIVE_DIRECTORY}
postgis=${2:?usage: verify.sh CORE_ARCHIVE_DIRECTORY POSTGIS_ARCHIVE_DIRECTORY TIGER_ARCHIVE_DIRECTORY}
tiger=${3:?usage: verify.sh CORE_ARCHIVE_DIRECTORY POSTGIS_ARCHIVE_DIRECTORY TIGER_ARCHIVE_DIRECTORY}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core=$(cd "$core" && pwd)
postgis=$(cd "$postgis" && pwd)
tiger=$(cd "$tiger" && pwd)
mkdir -p "$tiger/static-analysis"
docker run --rm --platform "$docker_platform" -e PG_ARCHITECTURE="$architecture" \
  -e PG_VERSION="${PG_VERSION:-18.6}" \
  -v "$core:/core:ro" -v "$postgis:/postgis:ro" -v "$tiger:/tiger:ro" -v "$repo:/repo:ro" \
  -v "$tiger/static-analysis:/analysis" \
  --entrypoint bash pg-binaries-postgis-verifier /repo/scripts/tiger/verify-in-container.sh
