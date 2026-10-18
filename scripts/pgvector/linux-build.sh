#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core=${1:?usage: linux-build.sh CORE_ARCHIVE EXPECTED_CORE_SHA256 SOURCE_ARCHIVE OUTPUT_DIRECTORY}
expected_core_sha=${2:?usage: linux-build.sh CORE_ARCHIVE EXPECTED_CORE_SHA256 SOURCE_ARCHIVE OUTPUT_DIRECTORY}
source=${3:?usage: linux-build.sh CORE_ARCHIVE EXPECTED_CORE_SHA256 SOURCE_ARCHIVE OUTPUT_DIRECTORY}
out=${4:?usage: linux-build.sh CORE_ARCHIVE EXPECTED_CORE_SHA256 SOURCE_ARCHIVE OUTPUT_DIRECTORY}
core=$(cd "$(dirname "$core")" && pwd)/$(basename "$core")
source=$(cd "$(dirname "$source")" && pwd)/$(basename "$source")
mkdir -p "$out"; out=$(cd "$out" && pwd)
source_sha=$(python3 "$repo/tools/source_archive.py" pgvector 0.8.7 tar.gz --field sha256)
python3 "$repo/scripts/pgvector/archive_input.py" validate-source "$source" "$source_sha"
python3 "$repo/scripts/pgvector/archive_input.py" validate-core "$core" "${core}.sha256" "$expected_core_sha" 18.6 x86_64
docker build --platform linux/amd64 -f "$repo/scripts/pgvector/linux-build.Dockerfile" -t pg-binaries-pgvector-separate-linux "$repo"
image_id=$(docker image inspect pg-binaries-pgvector-separate-linux --format '{{.Id}}')
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "Invalid Docker image ID" >&2; exit 2; }
build_id=${BUILD_ID:-local-$(python3 -c 'import uuid; print(uuid.uuid4())')}
revision=${SOURCE_REVISION:-${GITHUB_SHA:-$(git -C "$repo" rev-parse HEAD)}}
docker run --rm --platform linux/amd64 \
  -e PG_VERSION=18.6 -e PG_ARCHITECTURE=x86_64 -e VECTOR_SOURCE_SHA256="$source_sha" \
  -e EXPECTED_CORE_SHA256="$expected_core_sha" \
  -e BUILD_ID="$build_id" -e SOURCE_REVISION="$revision" -e BUILDER_IMAGE_ID="$image_id" \
  -v "$(dirname "$core"):/input:ro" -e CORE_ARCHIVE="$(basename "$core")" \
  -v "$(dirname "$source"):/source:ro" -e SOURCE_ARCHIVE="$(basename "$source")" \
  -v "$out:/out" pg-binaries-pgvector-separate-linux
