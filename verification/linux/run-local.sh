#!/usr/bin/env bash
set -euo pipefail

target=linux-arm64
if [[ ${1:-} == --target ]]; then
  target=${2:-}
  shift 2
fi
case "$target" in
  linux-arm64) platform=linux/arm64 ;;
  linux-x86_64) platform=linux/amd64 ;;
  *) echo "Unsupported Linux verification target: $target" >&2; exit 2 ;;
esac

if (( $# < 2 )); then
  echo "usage: $0 [--target TARGET] POSTGRESQL_ARCHIVE OUTPUT_DIRECTORY [PACKAGE=ARCHIVE ...]" >&2
  exit 2
fi
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
postgresql_archive=$1
output_directory=$2
shift 2
[[ -f $postgresql_archive ]] || { echo "Missing archive: $postgresql_archive" >&2; exit 1; }
mkdir -p "$output_directory"
output_directory=$(cd "$output_directory" && pwd)
postgresql_directory=$(cd "$(dirname "$postgresql_archive")" && pwd)
postgresql_name=$(basename "$postgresql_archive")

image=pg-binaries-${target}-verifier
docker build --platform "$platform" --build-arg "VERIFY_UID=$(id -u)" \
  -f "$repo/verification/linux/Dockerfile" -t "$image" "$repo" >/dev/null

mounts=(-v "$repo:/src:ro" -v "$postgresql_directory:/archives/postgresql:ro")
arguments=("/archives/postgresql/$postgresql_name" /home/verifier/results --target "$target")
index=0
for selection in "$@"; do
  package=${selection%%=*}
  archive=${selection#*=}
  [[ $selection == *=* && $package =~ ^[a-z][a-z0-9_]*$ && -f $archive ]] || {
    echo "Invalid package archive selection: $selection" >&2
    exit 2
  }
  directory=$(cd "$(dirname "$archive")" && pwd)
  name=$(basename "$archive")
  mounts+=(-v "$directory:/archives/extension$index:ro")
  arguments+=(--package-archive "$package=/archives/extension$index/$name")
  ((index+=1))
done

container=$(docker create --platform "$platform" "${mounts[@]}" \
  "$image" "${arguments[@]}")
trap 'docker rm -f "$container" >/dev/null 2>&1 || true' EXIT
docker start -a "$container" || true
status=$(docker inspect --format '{{.State.ExitCode}}' "$container")
docker cp "$container:/home/verifier/results/." "$output_directory" 2>/dev/null || true
exit "$status"
