#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
extension=${1:?usage: linux-verify.sh EXTENSION_ARCHIVE_DIRECTORY CORE_ARCHIVE_DIRECTORY}
core=${2:?usage: linux-verify.sh EXTENSION_ARCHIVE_DIRECTORY CORE_ARCHIVE_DIRECTORY}
extension=$(cd "$extension" && pwd)
core=$(cd "$core" && pwd)
mkdir -p "$extension/static-analysis"
docker build --platform linux/amd64 -f "$repo/scripts/pg_repack/linux-verify.Dockerfile" -t pg-binaries-pg-repack-alpine-probe "$repo"
docker run --rm --platform linux/amd64 -e PG_VERSION="${PG_VERSION:-18.6}" -v "$extension:/extension:ro" -v "$core:/core:ro" -v "$extension/static-analysis:/analysis" pg-binaries-pg-repack-alpine-probe
