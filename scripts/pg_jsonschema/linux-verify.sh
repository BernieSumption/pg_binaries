#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
archives=${1:?usage: linux-verify.sh ARCHIVE_DIRECTORY}
archives=$(cd "$archives" && pwd)
mkdir -p "$archives/static-analysis"
docker build --platform linux/amd64 -f "$repo/scripts/pg_jsonschema/linux-verify.Dockerfile" \
  -t pg-binaries-pg-jsonschema-alpine-probe "$repo"
docker run --rm --platform linux/amd64 -v "$archives:/archives:ro" \
  -v "$archives/static-analysis:/analysis" pg-binaries-pg-jsonschema-alpine-probe
