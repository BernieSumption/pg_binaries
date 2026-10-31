#!/usr/bin/env bash
set -euo pipefail

if (( $# < 3 || $# > 5 )); then
  echo "usage: $0 PACKAGE POSTGRESQL_DEVELOPMENT_ARCHIVE OUTPUT_DIRECTORY [TARGET] [CONTAINER_NAME]" >&2
  exit 2
fi
package=$1
development_archive=$2
output_directory=$3
target=${4:-linux-arm64}
container_name=${5:-pg-binaries-${target}-dev}
case "$target" in
  linux-arm64|linux-x86_64) ;;
  *) echo "Unsupported Linux development target: $target" >&2; exit 2 ;;
esac
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
[[ -f $development_archive ]] || { echo "Missing development archive: $development_archive" >&2; exit 1; }
[[ -f $repo/packages/$package/build.json ]] || {
  echo "Unknown extension package: $package" >&2
  exit 1
}
development_archive=$(cd "$(dirname "$development_archive")" && pwd)/$(basename "$development_archive")
mkdir -p "$output_directory"
output_directory=$(cd "$output_directory" && pwd)
if command -v shasum >/dev/null; then
  development_sha=$(shasum -a 256 "$development_archive" | awk '{print $1}')
else
  development_sha=$(sha256sum "$development_archive" | awk '{print $1}')
fi
container=$(bash "$repo/platforms/linux/dev-container.sh" "$target" "$container_name")
base="/work/local-iteration/$target/$package"
workspace="$base/workspace"
container_output="$base/output"
development_cache=/work/local-iteration/development-cache
development_copy="$development_cache/$development_sha.tar.gz"
docker exec "$container" mkdir -p "$base" "$container_output" "$development_cache"
if ! docker exec "$container" test -f "$development_copy"; then
  temporary_copy="$development_copy.$$.tmp"
  docker cp "$development_archive" "$container:$temporary_copy"
  docker exec "$container" mv -f "$temporary_copy" "$development_copy"
fi
docker exec -e CARGO_HOME=/work/cargo -e RUSTUP_HOME=/work/rustup "$container" bash -c '
  set -euo pipefail
  actual=$(sha256sum "$1" | cut -d " " -f1)
  [[ $actual == "$2" ]] || { echo "Cached PostgreSQL development archive checksum mismatch" >&2; exit 1; }
  python3 build.py --target "$3" extension-build "$4" "$1" "$5" \
    --workspace "$6" --source-cache /work/source-cache --reuse-workspace
' _ "$development_copy" "$development_sha" "$target" "$package" "$container_output" "$workspace"
docker cp "$container:$container_output/." "$output_directory/"
