#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
out=${1:?usage: verify.sh ARCHIVE_DIRECTORY}
out=$(cd "$out" && pwd)
docker build --platform linux/amd64 -f "$repo/scripts/linux/verify.Dockerfile" -t pg-binaries-linux-verifier "$repo"
docker run --rm --platform linux/amd64 -v "$out:/out:ro" -v "$repo/tests:/tests:ro" pg-binaries-linux-verifier
