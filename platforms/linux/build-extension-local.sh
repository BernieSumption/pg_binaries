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
[[ -f $repo/packages/$package/build.json ]] || {
  echo "Unknown extension package: $package" >&2
  exit 1
}
development_archive=$(cd "$(dirname "$development_archive")" && pwd)/$(basename "$development_archive")
mkdir -p "$output_directory"
output_directory=$(cd "$output_directory" && pwd)
container=$(bash "$repo/platforms/linux/dev-container.sh")
job=$(docker exec "$container" mktemp -d /work/extension.XXXXXX)
docker cp "$development_archive" "$container:$job/development.tar.gz"
docker exec -e CARGO_HOME=/work/cargo -e RUSTUP_HOME=/work/rustup "$container" bash -c '
  set -euo pipefail
  python3 build.py --target linux-arm64 prepare-dependencies "$1"
  python3 build.py --target linux-arm64 extension-build "$1" "$2/development.tar.gz" "$2/output" --workspace "$2/workspace" --source-cache /work/source-cache
' _ "$package" "$job"
docker cp "$container:$job/output/." "$output_directory/"
