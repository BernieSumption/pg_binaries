#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
target=${1:-linux-arm64}
name=${2:-pg-binaries-${target}-dev}
case "$target" in
  linux-arm64) platform=linux/arm64 ;;
  linux-x86_64) platform=linux/amd64 ;;
  *) echo "Unsupported Linux development target: $target" >&2; exit 2 ;;
esac
image=pg-binaries-${target}-dev
default_work="$repo/out/local-environments/$name"
work=${PG_BINARIES_LINUX_WORK:-$default_work}
mkdir -p "$work"
work=$(cd "$work" && pwd)

if ! docker container inspect "$name" >/dev/null 2>&1; then
  docker build --platform "$platform" -f "$repo/platforms/linux/Dockerfile.build" -t "$image" "$repo" >/dev/null
  docker create --name "$name" --platform "$platform" \
    -v "$repo:/repo:ro" -v "$work:/work" -w /repo "$image" sleep infinity >/dev/null
fi
if [[ $(docker inspect --format '{{.State.Running}}' "$name") != true ]]; then
  docker start "$name" >/dev/null
fi
printf '%s\n' "$name"
