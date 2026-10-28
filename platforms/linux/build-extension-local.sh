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
version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["postgresql"]["version"])' "$repo/support.json")
archive="$package-postgresql-$version-linux-arm64.tar.gz"

container=$(bash "$repo/platforms/linux/dev-container.sh")
docker exec "$container" mkdir -p /work/input /work/output
docker cp "$development_archive" "$container:/work/input/development.tar.gz"
docker exec "$container" rm -f "/work/output/$archive" "/work/output/$archive.sha256"
docker exec -e CARGO_HOME=/work/cargo -e RUSTUP_HOME=/work/rustup -e PGRX_HOME=/work/pgrx "$container" bash -c '
  set -euo pipefail
  rm -rf /opt/postgresql
  tar -xzf /work/input/development.tar.gz -C /opt
  python3 build.py --target linux-arm64 extension-build "$1" /opt/postgresql /work/output
' _ "$package"
docker cp "$container:/work/output/$archive" "$output_directory/$archive"
docker cp "$container:/work/output/$archive.sha256" "$output_directory/$archive.sha256"
