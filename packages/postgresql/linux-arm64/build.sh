#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
output_arg=${1:?usage: build.sh OUTPUT_DIRECTORY}
output=$(mkdir -p "$output_arg" && cd "$output_arg" && pwd)
docker build --platform linux/arm64 -f "$repo_root/packages/postgresql/linux-arm64/Dockerfile" -t pg-binaries-postgresql-linux-arm64 "$repo_root"
docker run --rm --platform linux/arm64 -v "$output:/out" pg-binaries-postgresql-linux-arm64
