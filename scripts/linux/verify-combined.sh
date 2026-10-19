#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core=$(cd "${1:?usage: verify-combined.sh CORE_DIR POSTGIS_DIR RESULTS_DIR}" && pwd)
postgis=${2:?usage: verify-combined.sh CORE_DIR POSTGIS_DIR RESULTS_DIR}
results=${3:?usage: verify-combined.sh CORE_DIR POSTGIS_DIR RESULTS_DIR}
mkdir -p "$postgis" "$results"
postgis=$(cd "$postgis" && pwd)
results=$(cd "$results" && pwd)
rm -rf "$results/status" "$results/logs" "$results/static-analysis" "$results/diagnostics"
rm -f "$core/publication/static-analysis/core-pgvector.json" \
  "$postgis/static-analysis/postgis.json"
rm -rf "$core/diagnostics"

pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac

docker build --platform "$docker_platform" -f "$repo/scripts/linux/combined-verify.Dockerfile" \
  -t pg-binaries-linux-verifier "$repo"
set +e
docker run --rm --platform "$docker_platform" \
  -e PG_VERSION="$pg_version" -e PG_ARCHITECTURE="$architecture" \
  -e GITHUB_RUN_ID -e GITHUB_REPOSITORY -e GITHUB_SERVER_URL -e GITHUB_SHA \
  -v "$core:/archives/core:ro" -v "$postgis:/archives/postgis:ro" \
  -v "$results:/results" \
  pg-binaries-linux-verifier
outcome=$?
set -e

mkdir -p "$core/publication/static-analysis" "$postgis/static-analysis"
if [[ -f "$results/static-analysis/core/core-pgvector.json" ]]; then
  cp "$results/static-analysis/core/core-pgvector.json" "$core/publication/static-analysis/"
fi
if [[ -f "$results/static-analysis/postgis/postgis.json" ]]; then
  cp "$results/static-analysis/postgis/postgis.json" "$postgis/static-analysis/"
fi
if [[ -d "$results/diagnostics" ]]; then
  mkdir -p "$core/diagnostics"
  cp -R "$results/diagnostics/." "$core/diagnostics/"
fi
exit "$outcome"
