#!/usr/bin/env bash
set -euo pipefail

os=$1 arch=$2 workspace=$3
exec bash "$(dirname "${BASH_SOURCE[0]}")/internal/dependencies/build.sh" "$os" "$arch" "$workspace"
