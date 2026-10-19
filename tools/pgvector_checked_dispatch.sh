#!/usr/bin/env bash
set -euo pipefail

request=${1:?usage: pgvector_checked_dispatch.sh REQUEST_JSON OUTPUT_JSON VERSION POSTGRESQL_VERSION}
output=${2:?usage: pgvector_checked_dispatch.sh REQUEST_JSON OUTPUT_JSON VERSION POSTGRESQL_VERSION}
version=${3:?usage: pgvector_checked_dispatch.sh REQUEST_JSON OUTPUT_JSON VERSION POSTGRESQL_VERSION}
postgresql_version=${4:?usage: pgvector_checked_dispatch.sh REQUEST_JSON OUTPUT_JSON VERSION POSTGRESQL_VERSION EVIDENCE_JSON}
evidence=${5:?usage: pgvector_checked_dispatch.sh REQUEST_JSON OUTPUT_JSON VERSION POSTGRESQL_VERSION EVIDENCE_JSON}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
candidate_dir=${RUNNER_TEMP:?}/pgvector-candidate
candidate_manifest=$candidate_dir/bundle.json
candidate_error=$candidate_dir/retrieval-error.txt
validation_error=$candidate_dir/validation-error.txt
dispatch_error=$candidate_dir/dispatch-error.txt
retrieval_outcome=not_attempted
validation_outcome=not_attempted
dispatch_outcome=not_written

write_evidence() {
  local exit_code=$?
  python3 "$repo/tools/pgvector_plan_evidence.py" \
    --request "$request" --candidate-manifest "$candidate_manifest" \
    --dispatch-plan "$output" --retrieval-outcome "$retrieval_outcome" \
    --validation-outcome "$validation_outcome" --dispatch-outcome "$dispatch_outcome" \
    --exit-code "$exit_code" --retrieval-error-file "$candidate_error" \
    --validation-error-file "$validation_error" --dispatch-error-file "$dispatch_error" \
    --output "$evidence" || true
}
trap write_evidence EXIT

mkdir -p "$candidate_dir"
if python3 "$repo/tools/pgvector_candidate_bundle.py" \
    --repository "${GITHUB_REPOSITORY:?}" --branch "${GITHUB_REF_NAME:?}" \
    --current-run-id "${GITHUB_RUN_ID:?}" --version "$version" \
    --postgresql-version "$postgresql_version" --architecture x86_64 \
    --output-directory "$candidate_dir" \
    --manifest-path "$candidate_manifest" 2> "$candidate_error"; then
  retrieval_outcome=retrieved
  docker pull --platform linux/amd64 ubuntu:22.04
  base_ref=$(docker image inspect ubuntu:22.04 --format '{{index .RepoDigests 0}}')
  base_digest=${base_ref##*@}
  docker build --pull --platform linux/amd64 -f "$repo/scripts/linux/Dockerfile" \
    -t pg-binaries-linux-pilot "$repo"
  core_packages=$(docker run --rm --platform linux/amd64 --entrypoint dpkg-query \
    pg-binaries-linux-pilot -W \
    -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n' \
    | LC_ALL=C sort | sha256sum | awk '{print $1}')
  docker build --platform linux/amd64 -f "$repo/scripts/pgvector/linux-build.Dockerfile" \
    -t pg-binaries-pgvector-separate-linux "$repo"
  vector_packages=$(docker run --rm --platform linux/amd64 --entrypoint dpkg-query \
    pg-binaries-pgvector-separate-linux -W \
    -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n' \
    | LC_ALL=C sort | sha256sum | awk '{print $1}')
  if python3 "$repo/tools/dispatch_plan.py" --request "$request" \
      --pgvector-candidate-bundle "$candidate_dir/bundle.json" \
      --core-base-image-digest "$base_digest" \
      --core-builder-packages-sha256 "$core_packages" \
      --pgvector-builder-packages-sha256 "$vector_packages" > "$output" 2> "$validation_error"; then
    validation_outcome=passed
    dispatch_outcome=checked_candidate
    cat "$validation_error" >&2
    exit 0
  fi
  validation_outcome=failed
  cat "$validation_error" >&2
else
  retrieval_outcome=failed
  cat "$candidate_error" >&2
fi

if python3 "$repo/tools/dispatch_plan.py" --request "$request" > "$output" 2> "$dispatch_error"; then
  dispatch_outcome=fallback
  cat "$dispatch_error" >&2
else
  planner_exit_code=$?
  dispatch_outcome=failed
  cat "$dispatch_error" >&2
  exit "$planner_exit_code"
fi
