#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
out=${1:?usage: build.sh OUTPUT_DIRECTORY}
mkdir -p "$out"
out=$(cd "$out" && pwd)
docker build --platform linux/amd64 -f "$repo/scripts/linux/Dockerfile" -t pg-binaries-linux-pilot "$repo"
docker run --rm --platform linux/amd64 -v "$out:/out" pg-binaries-linux-pilot
