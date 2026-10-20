#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
version=${1:?usage: resolve-core.sh POSTGRESQL_VERSION ARCH OUTPUT_DIRECTORY}
architecture=${2:?usage: resolve-core.sh POSTGRESQL_VERSION ARCH OUTPUT_DIRECTORY}
out=${3:?usage: resolve-core.sh POSTGRESQL_VERSION ARCH OUTPUT_DIRECTORY}
case "$architecture" in x86_64|arm64) ;; *) echo "Unsupported Linux architecture: $architecture" >&2; exit 2 ;; esac
case "$architecture" in x86_64) docker_platform=linux/amd64 ;; arm64) docker_platform=linux/arm64 ;; esac
if [[ ! $version =~ ^[1-9][0-9]*\.[0-9]+$ ]]; then
  echo "Unsupported PostgreSQL version: $version" >&2
  exit 2
fi
mkdir -p "$out"
out=$(cd "$out" && pwd)
rm -f "$out/core-resolution.json"
core_name="postgresql-$version-linux-$architecture.tar.gz"
candidate_fresh=false
candidate_json=
prepare_candidate_inputs() {
  docker pull --platform "$docker_platform" ubuntu:22.04 >/dev/null || return 1
  base_image_ref=$(docker image inspect ubuntu:22.04 --format '{{index .RepoDigests 0}}') || return 1
  base_image_digest=${base_image_ref##*@}
  [[ $base_image_digest =~ ^sha256:[0-9a-f]{64}$ ]] || return 1
  docker build --pull --platform "$docker_platform" -f "$repo/scripts/linux/Dockerfile" \
    -t pg-binaries-linux-pilot "$repo" >/dev/null || return 1
  builder_packages_sha256=$(docker run --rm --platform "$docker_platform" \
    --entrypoint dpkg-query pg-binaries-linux-pilot \
    -W -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n' \
    | LC_ALL=C sort | sha256sum | awk '{print $1}') || return 1
  [[ $builder_packages_sha256 =~ ^[0-9a-f]{64}$ ]]
}
pin_output=$(python3 "$repo/tools/linux_core_pin.py" "$version" "$architecture") || pin_status=$?
pin_status=${pin_status:-0}
if (( pin_status == 0 )); then
  pin_run_id=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["run_id"])' "$pin_output")
  pin_workflow=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["workflow"])' "$pin_output")
  pin_artifact=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["artifact_name"])' "$pin_output")
  pin_sha=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["sha256"])' "$pin_output")
  pin_archive=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["archive_name"])' "$pin_output")
  rm -f "$out/$core_name" "$out/$core_name.sha256" "$out/core-candidate-manifest.json"
  if gh run download "$pin_run_id" --name "$pin_artifact" --dir "$out"; then
    if [[ $pin_archive == "$core_name" && -s "$out/$core_name" ]]; then
      actual_sha=$(sha256sum "$out/$core_name" | awk '{print $1}')
      if [[ $actual_sha == "$pin_sha" ]]; then
        if run_json=$(gh api "repos/${GITHUB_REPOSITORY:?required for pinned core provenance}/actions/runs/$pin_run_id"); then
          if python3 - "$run_json" "$pin_run_id" "$pin_workflow" "${GITHUB_REPOSITORY}" "${GITHUB_REF_NAME:?required for pinned core provenance}" "$out/$core_name" "$pin_artifact" "$out/core-candidate-manifest.json" <<'PY'
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile

run = json.loads(sys.argv[1])
run_id, workflow, repository, branch, archive_path, artifact_name, manifest_path = sys.argv[2:]
repo = run.get("repository") if isinstance(run, dict) else None
head_repo = run.get("head_repository") if isinstance(run, dict) else None
revision = run.get("head_sha") if isinstance(run, dict) else None
attempt = run.get("run_attempt") if isinstance(run, dict) else None
if (not isinstance(repo, dict) or str(repo.get("full_name", "")).casefold() != repository.casefold()
        or not isinstance(head_repo, dict) or str(head_repo.get("full_name", "")).casefold() != repository.casefold()
        or str(run.get("id")) != run_id or run.get("head_branch") != branch
        or run.get("event") not in {"push", "workflow_dispatch"}
        or run.get("status") != "completed" or run.get("conclusion") != "success"
        or str(run.get("path", "")).rsplit("/", 1)[-1] != workflow
        or not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1
        or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision)):
    raise SystemExit("pinned Linux core producer run does not match its pin")
with tarfile.open(archive_path, "r:gz") as archive:
    info = archive.getmember("postgresql/manifest.json")
    member = archive.extractfile(info)
    if member is None or not info.isfile() or info.size > 1024 * 1024:
        raise SystemExit("pinned Linux core has no bounded regular manifest")
    core = json.load(member)
row = {"component": "postgresql", "project": "PostgreSQL", "version": core.get("version"),
       "platform": f"linux-{core.get('architecture')}", "postgresql_version": core.get("version"),
       "path": str(Path(archive_path).resolve()),
       "sha256": hashlib.sha256(Path(archive_path).read_bytes()).hexdigest(),
       "source": {"provider": "github-actions", "run_id": run_id, "run_attempt": attempt,
                  "head_sha": revision, "artifact_name": artifact_name}}
Path(manifest_path).write_text(json.dumps({"schema_version": 1, "archives": [row]}, indent=2) + "\n",
                               encoding="utf-8")
PY
          then
            if prepare_candidate_inputs; then
              if candidate_json=$(python3 "$repo/tools/linux_core_candidate.py" \
                --manifest "$out/core-candidate-manifest.json" --archive "$out/$core_name" \
                --postgresql-version "$version" --architecture "$architecture" \
                --artifact-name-template "$pin_artifact" \
                --base-image-digest "$base_image_digest" \
                --builder-packages-sha256 "$builder_packages_sha256" --root "$repo"); then
                candidate_fresh=true
              fi
            fi
            if [[ $candidate_fresh != true ]]; then
              rm -f "$out/$core_name" "$out/$core_name.sha256" "$out/core-candidate-manifest.json"
            fi
          fi
        fi
      fi
    fi
  fi
elif (( pin_status != 3 )); then
  exit "$pin_status"
fi

if [[ $candidate_fresh == true ]]; then
  echo "Using the checksum-verified pinned PostgreSQL $version core from Actions run $pin_run_id."
else
  rm -f "$out/$core_name" "$out/$core_name.sha256" "$out/core-candidate-manifest.json"
  echo "No usable unpublished Linux core pin exists; building the selected PostgreSQL core in Docker."
  PG_VERSION="$version" PG_ARCHITECTURE="$architecture" CORE_ONLY=1 \
    "$repo/scripts/linux/build.sh" "$out"
fi
record_args=(--archive "$out/$core_name" --output "$out/core-resolution.json"
  --postgresql-version "$version" --architecture "$architecture")
if [[ $candidate_fresh == true ]]; then
  record_args+=(--origin reused --candidate-json "$candidate_json"
    --candidate-manifest "$out/core-candidate-manifest.json")
else
  record_args+=(--origin built)
fi
python3 "$repo/tools/linux_core_resolution.py" "${record_args[@]}"
printf '%s\n' "$out/$core_name"
