#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
output=${1:?usage: build.sh OUTPUT_DIRECTORY}
mkdir -p "$output"
output=$(cd "$output" && pwd)
docker build --platform linux/amd64 -f "$repo/scripts/address_standardizer/Dockerfile" \
  -t pg-binaries-address-standardizer-pilot "$repo"
if ! docker run --rm --platform linux/amd64 -v "$output:/out" \
  pg-binaries-address-standardizer-pilot >"$output/build.log" 2>&1; then
  tail -n 120 "$output/build.log" >&2
  exit 1
fi
tail -n 60 "$output/build.log"
