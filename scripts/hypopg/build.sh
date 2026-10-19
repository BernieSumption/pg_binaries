#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
input=${1:?usage: build.sh LINUX_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
output=${2:?usage: build.sh LINUX_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY}
architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
input=$(cd "$input" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
docker build --platform "$docker_platform" -f "$repo/scripts/hypopg/Dockerfile" -t pg-binaries-hypopg-pilot "$repo"
pg_version=${PG_VERSION:-18.6}
package_inventory=$(mktemp)
build_inputs=$(mktemp)
trap 'rm -f "$package_inventory" "$build_inputs"' EXIT
docker run --rm --platform "$docker_platform" --entrypoint dpkg-query pg-binaries-hypopg-pilot \
  -W -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n' \
  | LC_ALL=C sort > "$package_inventory"
packages_sha256=$(sha256sum "$package_inventory" | cut -d ' ' -f 1)
core_sha256=$(sha256sum "$input/postgresql-$pg_version-linux-$architecture.tar.gz" | cut -d ' ' -f 1)
python3 "$repo/scripts/hypopg/build_inputs.py" \
  --core-sha256 "$core_sha256" --builder-packages-sha256 "$packages_sha256" \
  --postgresql-version "$pg_version" --architecture "$architecture" > "$build_inputs"
docker run --rm -e PG_ARCHITECTURE="$architecture" -e PG_VERSION="$pg_version" --platform "$docker_platform" \
  -v "$input:/input:ro" -v "$output:/out" -v "$build_inputs:/build_inputs.json:ro" pg-binaries-hypopg-pilot
