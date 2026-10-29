#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 2 ]] || { echo "usage: $0 OS ARCH [source selections...] POSTGRESQL_PREFIX OUTPUT_DIR" >&2; exit 2; }
os=$1 arch=$2
shift 2
case "$os-$arch" in
  macos-arm64|macos-x86_64|linux-arm64|linux-x86_64) ;;
  *) echo "Unsupported target: $os-$arch" >&2; exit 2 ;;
esac
recipe="$(dirname "${BASH_SOURCE[0]}")/$os/build.sh"
if [[ -f $recipe ]]; then
  exec bash "$recipe" "$arch" "$@"
fi
recipe="$(dirname "${BASH_SOURCE[0]}")/$os-$arch/build.sh"
[[ -f $recipe ]] || { echo "No recipe for $os-$arch" >&2; exit 2; }
exec bash "$recipe" "$@"
