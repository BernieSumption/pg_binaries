#!/usr/bin/env bash
set -euo pipefail

request=${1:?usage: hypopg_checked_dispatch.sh REQUEST_JSON OUTPUT_JSON VERSION POSTGRESQL_VERSION ARCHITECTURE}
output=${2:?usage: hypopg_checked_dispatch.sh REQUEST_JSON OUTPUT_JSON VERSION POSTGRESQL_VERSION ARCHITECTURE}
version=${3:?usage: hypopg_checked_dispatch.sh REQUEST_JSON OUTPUT_JSON VERSION POSTGRESQL_VERSION ARCHITECTURE}
postgresql_version=${4:?usage: hypopg_checked_dispatch.sh REQUEST_JSON OUTPUT_JSON VERSION POSTGRESQL_VERSION ARCHITECTURE}
architecture=${5:?usage: hypopg_checked_dispatch.sh REQUEST_JSON OUTPUT_JSON VERSION POSTGRESQL_VERSION ARCHITECTURE}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
candidate_dir=${RUNNER_TEMP:?}/hypopg-candidate
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac

if python3 "$repo/tools/hypopg_linux_candidate.py" \
    --repository "${GITHUB_REPOSITORY:?}" --branch "${GITHUB_REF_NAME:?}" \
    --current-run-id "${GITHUB_RUN_ID:?}" --extension-version "$version" \
    --postgresql-version "$postgresql_version" --architecture "$architecture" \
    --output-directory "$candidate_dir" \
    --manifest-path "$candidate_dir/bundle.json"; then
  docker pull --platform "$docker_platform" ubuntu:22.04
  base_ref=$(docker image inspect ubuntu:22.04 --format '{{index .RepoDigests 0}}')
  base_digest=${base_ref##*@}
  docker build --pull --platform "$docker_platform" -f "$repo/scripts/linux/Dockerfile" \
    -t pg-binaries-linux-pilot "$repo"
  core_packages=$(docker run --rm --platform "$docker_platform" --entrypoint dpkg-query \
    pg-binaries-linux-pilot -W \
    -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n' \
    | LC_ALL=C sort | sha256sum | awk '{print $1}')
  docker build --platform "$docker_platform" -f "$repo/scripts/hypopg/Dockerfile" \
    -t pg-binaries-hypopg-builder "$repo"
  hypopg_packages=$(docker run --rm --platform "$docker_platform" --entrypoint dpkg-query \
    pg-binaries-hypopg-builder -W \
    -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n' \
    | LC_ALL=C sort | sha256sum | awk '{print $1}')
  if python3 "$repo/tools/dispatch_plan.py" --request "$request" \
      --hypopg-candidate-bundle "$candidate_dir/bundle.json" \
      --core-base-image-digest "$base_digest" \
      --core-builder-packages-sha256 "$core_packages" \
      --hypopg-builder-packages-sha256 "$hypopg_packages" > "$output"; then
    exit 0
  fi
fi

python3 "$repo/tools/dispatch_plan.py" --request "$request" > "$output"
