#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
input=${1:?usage: verify.sh LINUX_ARCHIVE_DIRECTORY POSTGIS_ARCHIVE_DIRECTORY}
output=${2:?usage: verify.sh LINUX_ARCHIVE_DIRECTORY POSTGIS_ARCHIVE_DIRECTORY}
input=$(cd "$input" && pwd)
output=$(cd "$output" && pwd)
docker build --platform linux/amd64 -f "$repo/scripts/postgis/verify.Dockerfile" -t pg-binaries-postgis-verifier "$repo"
docker run --rm --platform linux/amd64 -v "$input:/input:ro" -v "$output:/out:ro" pg-binaries-postgis-verifier
