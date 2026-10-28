#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 2 ]] || { echo "usage: $0 OUTPUT_DIR [WORK_DIR]" >&2; exit 2; }
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
mkdir -p "$1"
output_dir=$(cd "$1" && pwd)
work_arg=${2:-$output_dir/work}
mkdir -p "$work_arg"
work_dir=$(cd "$work_arg" && pwd)

docker build --platform linux/arm64 -f "$repo/packages/postgresql/linux-arm64/Dockerfile" \
  -t pg-binaries-postgresql-linux-arm64 "$repo"
docker run --rm --platform linux/arm64 --entrypoint bash \
  -v "$repo:/repo:ro" -v "$output_dir:/out" -v "$work_dir:/work" -w /repo \
  pg-binaries-postgresql-linux-arm64 -c '
    set -euo pipefail
    python3 build.py --target linux-arm64 postgresql-build /work/dependencies /work/build /opt/postgresql
    python3 build.py --target linux-arm64 postgresql-package /opt/postgresql /work/dependencies /out
  '
