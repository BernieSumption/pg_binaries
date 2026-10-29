#!/usr/bin/env bash
set -euo pipefail
os=$1 arch=$2 workspace=$3
exec bash "$(dirname "${BASH_SOURCE[0]}")/internal/build-postgresql.sh" "$os" "$arch" "$workspace"
