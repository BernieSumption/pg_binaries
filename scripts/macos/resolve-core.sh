#!/usr/bin/env bash
set -euo pipefail

base_target=${1:?usage: resolve-core.sh BASE_TARGET OUTPUT_DIRECTORY}
output=${2:?usage: resolve-core.sh BASE_TARGET OUTPUT_DIRECTORY}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)

: "${GITHUB_REPOSITORY:?required for Actions candidate discovery}"
: "${GITHUB_REF_NAME:?required for Actions candidate discovery}"
: "${GITHUB_RUN_ID:?required for Actions candidate discovery}"
: "${GITHUB_RUN_ATTEMPT:?required for Actions candidate discovery}"

read -r version architecture core_name < <(python3 - "$base_target" <<'PY'
import json
import sys

target = json.load(open(sys.argv[1], encoding="utf-8"))
if target.get("platform") != "macos-arm64" or target.get("architecture") != "arm64":
    raise SystemExit("macOS core resolver currently supports only arm64")
version = target["postgresql_version"]
basename = f"postgresql-{version}-macos-arm64.tar.gz"
if target["core_archive"]["basename"] != basename:
    raise SystemExit("base target core archive name differs from selected version")
print(version, "arm64", basename)
PY
)

candidate_manifest="$output/candidate-manifest.json"
target="$output/target.json"
check_source_archive() {
  python3 - "$target" "$repo" <<'PY'
import json
from pathlib import Path
import sys
import tarfile

target = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
sys.path.insert(0, str(Path(sys.argv[2]) / "tools"))
from source_archive import source_archive

archive = Path(sys.argv[1]).parent / target["core_archive"]["basename"]
with tarfile.open(archive, "r:gz") as stream:
    manifest = json.load(stream.extractfile("postgresql/manifest.json"))
expected = source_archive("postgresql", target["postgresql_version"], "tar.bz2")
if manifest.get("source_archive") != expected:
    raise SystemExit("core archive source identity differs from the selected PostgreSQL release")
PY
}
candidate_usable=false
candidate_run_id=none
try_source() {
  local workflow=$1 artifact_template=$2 run_id run_attempt head_sha source_revision
  rm -f "$output/$core_name" "$output/$core_name.sha256" "$target"
  if ! python3 "$repo/tools/actions_candidate_discovery.py" \
      --repository "$GITHUB_REPOSITORY" --workflow "$workflow" \
      --branch "$GITHUB_REF_NAME" --current-run-id "$GITHUB_RUN_ID" \
      --artifact-name-template "$artifact_template" --archive-basename "$core_name" \
      --project postgresql --version "$version" --platform macos-arm64 \
      --postgresql-version "$version" --output-directory "$output" \
      --manifest-path "$candidate_manifest"; then
    echo "Cannot inspect checked macOS core candidates from $workflow" >&2
    exit 1
  fi
  read -r run_id run_attempt head_sha < <(python3 - "$candidate_manifest" <<'PY'
import json
import sys
rows = json.load(open(sys.argv[1], encoding="utf-8"))["archives"]
if len(rows) > 1:
    raise SystemExit("candidate discovery returned more than one core archive")
if rows:
    source = rows[0]["source"]
    print(source["run_id"], source["run_attempt"], source["head_sha"])
else:
    print("none none none")
PY
)
  [[ $run_id != none ]] || return 1
  if ! python3 "$repo/tools/macos_core_target_config.py" \
      --base-target "$base_target" --core-archive "$output/$core_name" \
      --source-run-id "$run_id" --source-run-attempt "$run_attempt" \
      --output "$target"; then
    return 1
  fi
  source_revision=$(python3 - "$target" <<'PY'
import json
import sys

print(json.load(open(sys.argv[1], encoding="utf-8"))["core_archive"]["source_revision"])
PY
)
  [[ $source_revision == "$head_sha" ]] || return 1
  if ! git -C "$repo" cat-file -e "$source_revision^{commit}" 2>/dev/null \
      && ! git -C "$repo" fetch --no-tags --depth=1 origin "$source_revision"; then
    return 1
  fi
  git -C "$repo" diff --quiet "$source_revision" HEAD -- \
    scripts/macos/build.sh scripts/macos/build-source-dependencies.sh \
    scripts/macos/bundle.py scripts/macos/licenses.py \
    tools/source_archive.py tools/discover_builtins.py \
    tools/create_macos_symbols.py && check_source_archive || return 1
  candidate_run_id=$run_id
  return 0
}

if try_source hypopg-macos-arm64-selected-publication.yml \
    "hypopg-macos-arm64-${version}-candidate-{run_id}"; then
  candidate_usable=true
elif try_source macos-arm64-pilot.yml macos-arm64-pilot-archives; then
  candidate_usable=true
fi

if [[ $candidate_usable == true ]]; then
  echo "Reusing checked PostgreSQL $version core from Actions run $candidate_run_id"
else
  echo "No current checked PostgreSQL $version core candidate; building on this macOS runner"
  rm -f "$output/$core_name" "$output/$core_name.sha256" "$target"
  bash "$repo/scripts/macos/build.sh" "$output" "$architecture" "$version" core-only
  python3 "$repo/tools/macos_core_target_config.py" \
    --base-target "$base_target" --core-archive "$output/$core_name" \
    --source-run-id "$GITHUB_RUN_ID" --source-run-attempt "$GITHUB_RUN_ATTEMPT" \
    --output "$target"
  check_source_archive
fi
