#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
name=pg-binaries-linux-arm64-dev
image=pg-binaries-linux-arm64-dev
work=${PG_BINARIES_LINUX_WORK:-${TMPDIR:-/tmp}/pg-binaries-linux-arm64-dev}
mkdir -p "$work"
work=$(cd "$work" && pwd)

if ! docker container inspect "$name" >/dev/null 2>&1; then
  docker build --platform linux/arm64 -f "$repo/platforms/linux/Dockerfile.build" -t "$image" "$repo" >/dev/null
  docker create --name "$name" --platform linux/arm64 \
    -v "$repo:/repo:ro" -v "$work:/work" -w /repo "$image" sleep infinity >/dev/null
fi
if [[ $(docker inspect --format '{{.State.Running}}' "$name") != true ]]; then
  docker start "$name" >/dev/null
fi
printf '%s\n' "$name"
