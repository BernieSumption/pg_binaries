#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
out=${1:?usage: build.sh OUTPUT_DIRECTORY}
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
source_revision=${SOURCE_REVISION:-${GITHUB_SHA:-}}
if [[ -z $source_revision ]]; then
  source_revision=$(git -C "$repo" rev-parse HEAD 2>/dev/null || true)
fi
if [[ ! $source_revision =~ ^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$ ]]; then
  echo "SOURCE_REVISION must be a full Git object ID: $source_revision" >&2
  exit 2
fi
build_id=${BUILD_ID:-}
if [[ -z $build_id ]]; then
  if [[ -n ${GITHUB_RUN_ID:-} ]]; then
    build_id="github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT:-1}"
  else
    build_id="local-$(python3 -c 'import uuid; print(uuid.uuid4())')"
  fi
fi
if [[ ! $build_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "BUILD_ID may contain only letters, digits, dot, underscore and hyphen" >&2
  exit 2
fi
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
if [[ ! $pg_version =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "Linux pilot currently supports PostgreSQL 15 through 18 minors only: $pg_version" >&2
  exit 2
fi
python3 "$repo/tools/plan_work.py" --select-linux-pilot "$pg_version" --architecture "$architecture" >/dev/null
pg_source_url=$(python3 "$repo/tools/source_archive.py" postgresql "$pg_version" tar.bz2 --field url)
pg_source_sha256=$(python3 "$repo/tools/source_archive.py" postgresql "$pg_version" tar.bz2 --field sha256)
vector_source_url=$(python3 "$repo/tools/source_archive.py" pgvector 0.8.7 tar.gz --field url)
vector_source_sha256=$(python3 "$repo/tools/source_archive.py" pgvector 0.8.7 tar.gz --field sha256)
mkdir -p "$out"
out=$(cd "$out" && pwd)
docker build --platform "$docker_platform" -f "$repo/scripts/linux/Dockerfile" -t pg-binaries-linux-pilot "$repo"
builder_image_id=$(docker image inspect pg-binaries-linux-pilot --format '{{.Id}}')
if [[ ! $builder_image_id =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "Docker did not provide a content-addressed Linux builder image ID" >&2
  exit 2
fi
docker run --rm --platform "$docker_platform" \
  -e PG_VERSION="$pg_version" -e PG_ARCHITECTURE="$architecture" \
  -e PG_SOURCE_URL="$pg_source_url" -e PG_SOURCE_SHA256="$pg_source_sha256" \
  -e VECTOR_SOURCE_URL="$vector_source_url" -e VECTOR_SOURCE_SHA256="$vector_source_sha256" \
  -e BUILD_ID="$build_id" -e SOURCE_REVISION="$source_revision" \
  -e BUILDER_IMAGE_ID="$builder_image_id" \
  -v "$out:/out" pg-binaries-linux-pilot
