#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
version=${1:?usage: resolve-core.sh POSTGRESQL_VERSION ARCH OUTPUT_DIRECTORY WORKFLOW ARTIFACT_TEMPLATE [WORKFLOW ARTIFACT_TEMPLATE ...]}
architecture=${2:?usage: resolve-core.sh POSTGRESQL_VERSION ARCH OUTPUT_DIRECTORY WORKFLOW ARTIFACT_TEMPLATE [WORKFLOW ARTIFACT_TEMPLATE ...]}
out=${3:?usage: resolve-core.sh POSTGRESQL_VERSION ARCH OUTPUT_DIRECTORY WORKFLOW ARTIFACT_TEMPLATE [WORKFLOW ARTIFACT_TEMPLATE ...]}
shift 3
if (( $# == 0 || $# % 2 != 0 )); then
  echo 'Provide one or more WORKFLOW ARTIFACT_TEMPLATE pairs.' >&2
  exit 2
fi
case "$architecture" in
  x86_64) docker_platform=linux/amd64 ;;
  arm64) docker_platform=linux/arm64 ;;
  *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;;
esac
for name in GH_TOKEN GITHUB_REPOSITORY GITHUB_REF_NAME GITHUB_RUN_ID; do
  if [[ -z ${!name:-} ]]; then
    echo "$name is required to resolve a Linux PostgreSQL core." >&2
    exit 2
  fi
done
if [[ ! $version =~ ^[1-9][0-9]*\.[0-9]+$ ]]; then
  echo "Unsupported PostgreSQL version: $version" >&2
  exit 2
fi
mkdir -p "$out"
out=$(cd "$out" && pwd)
core_name="postgresql-$version-linux-$architecture.tar.gz"
docker pull --platform "$docker_platform" ubuntu:22.04
base_image_ref=$(docker image inspect ubuntu:22.04 --format '{{index .RepoDigests 0}}')
base_image_digest=${base_image_ref##*@}
if [[ ! $base_image_digest =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo 'Docker did not provide Ubuntu base image provenance.' >&2
  exit 2
fi
docker build --pull --platform "$docker_platform" -f "$repo/scripts/linux/Dockerfile" \
  -t pg-binaries-linux-pilot "$repo"
builder_packages_sha256=$(docker run --rm --platform "$docker_platform" \
  --entrypoint dpkg-query pg-binaries-linux-pilot \
  -W -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n' \
  | LC_ALL=C sort | sha256sum | awk '{print $1}')
if [[ ! $builder_packages_sha256 =~ ^[0-9a-f]{64}$ ]]; then
  echo 'Could not identify Linux builder package inputs.' >&2
  exit 2
fi
candidate_fresh=false
while (( $# )); do
  source_workflow=$1
  artifact_template=$2
  shift 2
  if ! python3 "$repo/tools/actions_candidate_discovery.py" \
    --repository "$GITHUB_REPOSITORY" --workflow "$source_workflow" \
    --branch "$GITHUB_REF_NAME" --current-run-id "$GITHUB_RUN_ID" \
    --artifact-name-template "$artifact_template" \
    --archive-basename "$core_name" --project postgresql --version "$version" \
    --platform "linux-$architecture" --postgresql-version "$version" \
    --output-directory "$out" --manifest-path "$out/core-candidate-manifest.json"; then
    rm -f "$out/$core_name" "$out/$core_name.sha256"
    continue
  fi
  if [[ -s "$out/$core_name" && -s "$out/$core_name.sha256" ]] && \
    python3 "$repo/tools/linux_core_candidate.py" \
      --manifest "$out/core-candidate-manifest.json" --archive "$out/$core_name" \
      --postgresql-version "$version" --architecture "$architecture" \
      --artifact-name-template "$artifact_template" \
      --base-image-digest "$base_image_digest" \
      --builder-packages-sha256 "$builder_packages_sha256"; then
    candidate_fresh=true
    break
  fi
  rm -f "$out/$core_name" "$out/$core_name.sha256"
done
if [[ $candidate_fresh == true && -s "$out/$core_name" ]]; then
  echo 'Using a checksum-verified core candidate with matching source/run identity and builder inputs.'
else
  rm -f "$out/$core_name" "$out/$core_name.sha256"
  echo 'No fresh checked core candidate exists; building the selected PostgreSQL core in Docker.'
  PG_VERSION="$version" PG_ARCHITECTURE="$architecture" \
    "$repo/scripts/linux/build.sh" "$out"
fi
printf '%s\n' "$out/$core_name"
