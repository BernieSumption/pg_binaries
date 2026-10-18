#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
archives=${1:?usage: linux-verify.sh EXTENSION_ARCHIVE_DIRECTORY CORE_ARCHIVE_DIRECTORY}
core_archives=${2:?usage: linux-verify.sh EXTENSION_ARCHIVE_DIRECTORY CORE_ARCHIVE_DIRECTORY}
architecture=${PG_ARCHITECTURE:-x86_64}
pg_version=${PG_VERSION:-18.6}
case "$architecture" in x86_64) docker_platform=linux/amd64 ;; arm64) docker_platform=linux/arm64 ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
archives=$(cd "$archives" && pwd)
core_archives=$(cd "$core_archives" && pwd)
mkdir -p "$archives/static-analysis"
docker build --platform "$docker_platform" -f "$repo/scripts/address_standardizer/linux-verify.Dockerfile" \
  -t pg-binaries-address-standardizer-alpine-probe "$repo"
docker run --rm --platform "$docker_platform" -e PG_ARCHITECTURE="$architecture" -e PG_VERSION="$pg_version" \
  -v "$archives:/archives:ro" -v "$core_archives:/core:ro" -v "$archives/static-analysis:/analysis" \
  pg-binaries-address-standardizer-alpine-probe
