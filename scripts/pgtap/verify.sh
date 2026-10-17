#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core=${1:?usage: verify.sh LINUX_CORE_DIRECTORY PGTAP_ARCHIVE_DIRECTORY}
extension=${2:?usage: verify.sh LINUX_CORE_DIRECTORY PGTAP_ARCHIVE_DIRECTORY}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
core=$(cd "$core" && pwd)
extension=$(cd "$extension" && pwd)
mkdir -p "$extension/static-analysis"
docker build --platform "$docker_platform" -f "$repo/scripts/pgtap/verify.Dockerfile" -t pg-binaries-pgtap-verifier "$repo"
docker run --rm --platform "$docker_platform" -e PG_ARCHITECTURE="$architecture" -e PG_VERSION="${PG_VERSION:-18.6}" \
  -v "$core:/input:ro" -v "$extension:/extension:ro" \
  -v "$extension/static-analysis:/analysis" pg-binaries-pgtap-verifier
