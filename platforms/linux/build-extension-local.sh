#!/usr/bin/env bash
set -euo pipefail

if (( $# != 3 )); then
  echo "usage: $0 PACKAGE POSTGRESQL_DEVELOPMENT_ARCHIVE OUTPUT_DIRECTORY" >&2
  exit 2
fi
package=$1
development_archive=$2
output_directory=$3
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
[[ -f $development_archive ]] || { echo "Missing development archive: $development_archive" >&2; exit 1; }
[[ -f $repo/packages/$package/linux-arm64/build.sh ]] || {
  echo "No Linux ARM64 recipe for $package" >&2
  exit 1
}
development_archive=$(cd "$(dirname "$development_archive")" && pwd)/$(basename "$development_archive")
mkdir -p "$output_directory"
output_directory=$(cd "$output_directory" && pwd)

if [[ $package == postgis ]]; then
  docker build --platform linux/arm64 -f "$repo/packages/postgis/linux-arm64/Dockerfile" \
    -t pg-binaries-postgis-linux-arm64 "$repo/packages/postgis/linux-arm64" >/dev/null
  image=pg-binaries-postgis-linux-arm64
else
  docker build --platform linux/arm64 -f "$repo/packages/postgresql/linux-arm64/Dockerfile" \
    -t pg-binaries-postgresql-linux-arm64 "$repo" >/dev/null
  image=pg-binaries-postgresql-linux-arm64
  if [[ $package == pg_jsonschema ]]; then
    docker build --platform linux/arm64 -f "$repo/packages/pg_jsonschema/linux-arm64/Dockerfile" \
      -t pg-binaries-pg-jsonschema-linux-arm64 "$repo/packages/pg_jsonschema/linux-arm64" >/dev/null
    image=pg-binaries-pg-jsonschema-linux-arm64
  fi
fi

docker run --rm --platform linux/arm64 --entrypoint bash \
  -v "$repo:/repo:ro" -v "$development_archive:/input/development.tar.gz:ro" \
  -v "$output_directory:/out" -w /repo "$image" -c '
    set -euo pipefail
    mkdir -p /work/development
    tar -xzf /input/development.tar.gz -C /work/development
    mv /work/development/postgresql /opt/postgresql
    python3 build.py --target linux-arm64 extension-build "$1" /opt/postgresql /out
  ' _ "$package"
