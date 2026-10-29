#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 3 ]] || { echo "usage: $0 OS ARCH build|package|dependencies [arguments]" >&2; exit 2; }
os=$1 arch=$2 operation=$3
shift 3
case "$os-$arch" in
  macos-arm64|macos-x86_64|linux-arm64|linux-x86_64) ;;
  *) echo "Unsupported target: $os-$arch" >&2; exit 2 ;;
esac
case "$operation" in
  build) recipe=build.sh ;;
  package) recipe=package.sh ;;
  dependencies) recipe=build-dependencies.sh ;;
  *) echo "Unsupported PostgreSQL operation: $operation" >&2; exit 2 ;;
esac
path="$(dirname "${BASH_SOURCE[0]}")/$os-$arch/$recipe"
[[ -f $path ]] || { echo "No recipe for $os-$arch $operation" >&2; exit 2; }
exec bash "$path" "$@"
