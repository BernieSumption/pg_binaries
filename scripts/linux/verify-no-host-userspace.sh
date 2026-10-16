#!/usr/bin/env bash
set -euo pipefail

archives=${1:?usage: verify-no-host-userspace.sh ARCHIVE_DIRECTORY PG_VERSION ARCHITECTURE}
version=${2:?}
architecture=${3:?}
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
archive="$archives/postgresql-$version-linux-$architecture.tar.gz"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
tar -xzf "$archive" -C "$work"
docker build -q -f "$(dirname "$0")/empty-host.Dockerfile" -t pg-binaries-empty-host "$(dirname "$0")/../.." >/dev/null
actual=$(docker run --rm --platform "$docker_platform" \
  -v "$work/postgresql:/pg:ro" --entrypoint /pg/bin/postgres \
  pg-binaries-empty-host --version)
test "$actual" = "postgres (PostgreSQL) $version"
printf 'PASS: PostgreSQL %s launcher without host user space on %s\n' "$version" "$architecture"
