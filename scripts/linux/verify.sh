#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
out=${1:?usage: verify.sh ARCHIVE_DIRECTORY}
out=$(cd "$out" && pwd)
pg_version=${PG_VERSION:-18.6}
if [[ ! $pg_version =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Linux pilot currently supports PostgreSQL 15 through 18 minors only: $pg_version" >&2
  exit 2
fi
docker build --platform linux/amd64 -f "$repo/scripts/linux/verify.Dockerfile" -t pg-binaries-linux-verifier "$repo"
docker run --rm --platform linux/amd64 -e PG_VERSION="$pg_version" -v "$out:/out:ro" -v "$repo/tests:/tests:ro" pg-binaries-linux-verifier
