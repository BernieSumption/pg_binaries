#!/usr/bin/env bash
set -euo pipefail

os=$1 arch=$2 workspace=$3
internal=$(cd "$(dirname "${BASH_SOURCE[0]}")/internal/dependencies" && pwd)

case "$os" in
  linux) exec bash "$internal/linux.sh" "$os" "$arch" "$workspace" ;;
  macos) exec bash "$internal/macos.sh" "$os" "$arch" "$workspace" ;;
  *) echo "Unsupported PostGIS dependency target OS: $os" >&2; exit 2 ;;
esac
