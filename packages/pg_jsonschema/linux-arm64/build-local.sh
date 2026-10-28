#!/usr/bin/env bash
set -euo pipefail

[[ $# == 5 ]] || {
  echo "usage: $0 SOURCE_URL SOURCE_SHA256 VERSION POSTGRESQL_PREFIX OUTPUT_DIR" >&2
  exit 2
}
source_url=$1 source_sha=$2 version=$3 pg_prefix=$4 output_dir=$5
[[ -x "$pg_prefix/bin/pg_config" ]] || { echo "Missing PostgreSQL pg_config under $pg_prefix" >&2; exit 1; }
pg_prefix=$(cd "$pg_prefix" && pwd)
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
image=pg-binaries-pg-jsonschema-linux-arm64

docker build --platform linux/arm64 -f "$repo/packages/pg_jsonschema/linux-arm64/Dockerfile" -t "$image" "$repo/packages/pg_jsonschema/linux-arm64"
docker run --rm --platform linux/arm64 --entrypoint bash \
  -v "$repo:/repo" -v "$pg_prefix:/opt/postgresql" -v "$output_dir:/out" \
  "$image" /repo/packages/pg_jsonschema/linux-arm64/build.sh \
  "$source_url" "$source_sha" "$version" /opt/postgresql /out
