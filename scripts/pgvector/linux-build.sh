#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core=${1:?usage: linux-build.sh CORE_ARCHIVE EXPECTED_CORE_SHA256 SOURCE_ARCHIVE OUTPUT_DIRECTORY}
expected_core_sha=${2:?usage: linux-build.sh CORE_ARCHIVE EXPECTED_CORE_SHA256 SOURCE_ARCHIVE OUTPUT_DIRECTORY}
source=${3:?usage: linux-build.sh CORE_ARCHIVE EXPECTED_CORE_SHA256 SOURCE_ARCHIVE OUTPUT_DIRECTORY}
out=${4:?usage: linux-build.sh CORE_ARCHIVE EXPECTED_CORE_SHA256 SOURCE_ARCHIVE OUTPUT_DIRECTORY}
core=$(cd "$(dirname "$core")" && pwd)/$(basename "$core")
source=$(cd "$(dirname "$source")" && pwd)/$(basename "$source")
pg_version=${PG_VERSION:-18.6}
architecture=${PG_ARCHITECTURE:-x86_64}
vector_version=${PGVECTOR_VERSION:-0.8.7}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
if [[ ! "$pg_version" =~ ^(15|16|17|18)\.[0-9]+$ ]]; then
  echo "The Linux pgvector selected path supports PostgreSQL 15 through 18" >&2
  exit 2
fi
pg_major=${pg_version%%.*}
if [[ ! "$vector_version" =~ ^[0-9]+(\.[0-9]+)+$ ]]; then
  echo "PGVECTOR_VERSION must be a dotted numeric release" >&2
  exit 2
fi
mkdir -p "$out"; out=$(cd "$out" && pwd)
source_sha=$(python3 "$repo/tools/source_archive.py" pgvector "$vector_version" tar.gz --field sha256)
source_url=$(python3 "$repo/tools/source_archive.py" pgvector "$vector_version" tar.gz --field url)
core_source_sha=$(python3 "$repo/tools/source_archive.py" postgresql "$pg_version" tar.bz2 --field sha256)
python3 "$repo/scripts/pgvector/archive_input.py" validate-source "$source" "$source_sha" "$vector_version"
python3 "$repo/scripts/pgvector/archive_input.py" validate-core "$core" "${core}.sha256" "$expected_core_sha" "$pg_version" "$architecture" "$core_source_sha"
docker build --platform "$docker_platform" -f "$repo/scripts/pgvector/linux-build.Dockerfile" -t pg-binaries-pgvector-separate-linux "$repo"
image_id=$(docker image inspect pg-binaries-pgvector-separate-linux --format '{{.Id}}')
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "Invalid Docker image ID" >&2; exit 2; }
PG_ARCHITECTURE="$architecture" "$repo/scripts/pgvector/builder-packages.sh" "$out/builder-packages.tsv"
builder_packages_sha=$(sha256sum "$out/builder-packages.tsv" | awk '{print $1}')
python3 "$repo/scripts/pgvector/build_inputs.py" --pgvector-version "$vector_version" \
  --architecture "$architecture" --builder-packages-sha256 "$builder_packages_sha" \
  --core-sha256 "$expected_core_sha" --postgresql-major "$pg_major" \
  > "$out/build-input-identity.json"
build_id=${BUILD_ID:-local-$(python3 -c 'import uuid; print(uuid.uuid4())')}
revision=${SOURCE_REVISION:-${GITHUB_SHA:-$(git -C "$repo" rev-parse HEAD)}}
docker run --rm --platform "$docker_platform" \
  -e PG_VERSION="$pg_version" -e PG_ARCHITECTURE="$architecture" -e PGVECTOR_VERSION="$vector_version" \
  -e VECTOR_SOURCE_SHA256="$source_sha" -e VECTOR_SOURCE_URL="$source_url" \
  -e EXPECTED_CORE_SHA256="$expected_core_sha" \
  -e CORE_SOURCE_SHA256="$core_source_sha" \
  -e BUILD_ID="$build_id" -e SOURCE_REVISION="$revision" -e BUILDER_IMAGE_ID="$image_id" \
  -e BUILDER_PACKAGES_SHA256="$builder_packages_sha" \
  -v "$(dirname "$core"):/input:ro" -e CORE_ARCHIVE="$(basename "$core")" \
  -v "$(dirname "$source"):/source:ro" -e SOURCE_ARCHIVE="$(basename "$source")" \
  -v "$out:/out" pg-binaries-pgvector-separate-linux
