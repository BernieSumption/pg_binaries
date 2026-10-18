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
architecture = target.get("architecture")
if architecture not in {"arm64", "x86_64"} or target.get("platform") != f"macos-{architecture}":
    raise SystemExit("macOS core resolver supports only arm64 and x86_64")
version = target["postgresql_version"]
basename = f"postgresql-{version}-macos-{architecture}.tar.gz"
if target["core_archive"]["basename"] != basename:
    raise SystemExit("base target core archive name differs from selected version")
print(version, architecture, basename)
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
  local workflow=$1 artifact_template=$2 uploader_run_id builder_run_id builder_attempt source_revision builder_json
  rm -f "$output/$core_name" "$output/$core_name.sha256" "$target"
  if ! python3 "$repo/tools/actions_candidate_discovery.py" \
      --repository "$GITHUB_REPOSITORY" --workflow "$workflow" \
      --branch "$GITHUB_REF_NAME" --current-run-id "$GITHUB_RUN_ID" \
      --artifact-name-template "$artifact_template" --archive-basename "$core_name" \
      --project postgresql --version "$version" --platform "macos-$architecture" \
      --postgresql-version "$version" --output-directory "$output" \
      --manifest-path "$candidate_manifest"; then
    echo "Cannot inspect checked macOS core candidates from $workflow" >&2
    exit 1
  fi
  read -r uploader_run_id < <(python3 - "$candidate_manifest" <<'PY'
import json
import sys
rows = json.load(open(sys.argv[1], encoding="utf-8"))["archives"]
if len(rows) > 1:
    raise SystemExit("candidate discovery returned more than one core archive")
if rows:
    source = rows[0]["source"]
    print(source["run_id"])
else:
    print("none")
PY
)
  [[ $uploader_run_id != none ]] || return 1
  local builder_provenance
  if ! builder_provenance=$(python3 - "$output/$core_name" <<'PY'
import json
import re
import sys
import tarfile

with tarfile.open(sys.argv[1], "r:gz") as archive:
    members = archive.getmembers()
    if len(members) > 100_000:
        raise SystemExit("core archive has too many entries")
    names = [m.name for m in members]
    if len(names) != len(set(names)):
        raise SystemExit("core archive contains duplicate paths")
    matches = [m for m in members if m.name == "postgresql/manifest.json"]
    if len(matches) != 1 or not matches[0].isfile() or matches[0].size > 1024 * 1024:
        raise SystemExit("core archive must contain one bounded regular manifest")
    stream = archive.extractfile(matches[0])
    manifest = json.loads(stream.read(1024 * 1024 + 1).decode("utf-8"))
build_id = manifest.get("build_id") if isinstance(manifest, dict) else None
revision = manifest.get("source_revision") if isinstance(manifest, dict) else None
match = re.fullmatch(r"github-([1-9][0-9]*)-([1-9][0-9]*)", build_id or "")
if not match or not re.fullmatch(r"[0-9a-f]{40}", revision or ""):
    raise SystemExit("core archive manifest has invalid builder provenance")
print(match.group(1), match.group(2), revision)
PY
  ); then
    return 1
  fi
  read -r builder_run_id builder_attempt source_revision <<<"$builder_provenance"
  if ! builder_json=$(gh api "repos/$GITHUB_REPOSITORY/actions/runs/$builder_run_id"); then
    echo "Cannot inspect macOS core builder run $builder_run_id" >&2
    exit 1
  fi
  if ! python3 - "$builder_json" "$GITHUB_REPOSITORY" "$GITHUB_REF_NAME" \
      "$builder_run_id" "$builder_attempt" "$source_revision" "$architecture" <<'PY'
import json
import re
import sys

run = json.loads(sys.argv[1])
repository, branch, run_id, attempt, revision, architecture = sys.argv[2:]
suffix = "arm64" if architecture == "arm64" else "x86_64"
pilot = f"macos-{suffix}-pilot.yml" if architecture == "arm64" else "macos-pilot.yml"
allowed = {pilot, f"hypopg-macos-{suffix}-selected-publication.yml"}
if architecture == "arm64":
    allowed.add("pgtap-macos-arm64-selected-publication.yml")
repo = run.get("repository") if isinstance(run, dict) else None
head_repo = run.get("head_repository") if isinstance(run, dict) else None
valid = (isinstance(repo, dict) and str(repo.get("full_name", "")).casefold() == repository.casefold()
         and isinstance(head_repo, dict) and str(head_repo.get("full_name", "")).casefold() == repository.casefold()
         and str(run.get("id")) == run_id
         and isinstance(run.get("run_attempt"), int) and not isinstance(run.get("run_attempt"), bool)
         and run.get("run_attempt") == int(attempt)
         and run.get("head_branch") == branch and run.get("event") in {"push", "workflow_dispatch"}
         and run.get("status") == "completed" and run.get("conclusion") == "success"
         and str(run.get("path", "")).rsplit("/", 1)[-1] in allowed
         and run.get("head_sha") == revision and re.fullmatch(r"[0-9a-f]{40}", revision) is not None)
if not valid:
    raise SystemExit("core builder run identity, status, workflow, or revision does not match its manifest")
PY
  then
    return 1
  fi
  if ! python3 "$repo/tools/macos_core_target_config.py" \
      --base-target "$base_target" --core-archive "$output/$core_name" \
      --source-run-id "$builder_run_id" --source-run-attempt "$builder_attempt" \
      --output "$target"; then
    return 1
  fi
  if ! git -C "$repo" cat-file -e "$source_revision^{commit}" 2>/dev/null \
      && ! git -C "$repo" fetch --no-tags --depth=1 origin "$source_revision"; then
    return 1
  fi
  git -C "$repo" diff --quiet "$source_revision" HEAD -- \
    scripts/macos/build.sh scripts/macos/build-source-dependencies.sh \
    scripts/macos/bundle.py scripts/macos/licenses.py \
    tools/source_archive.py tools/discover_builtins.py \
    tools/create_macos_symbols.py && check_source_archive || return 1
  candidate_run_id=$builder_run_id
  return 0
}

if [[ $architecture == arm64 ]]; then
  selected_workflow=hypopg-macos-arm64-selected-publication.yml
  selected_artifact="hypopg-macos-arm64-${version}-candidate-{run_id}"
  pilot_workflow=macos-arm64-pilot.yml
else
  selected_workflow=hypopg-macos-x86_64-selected-publication.yml
  selected_artifact="hypopg-macos-x86_64-${version}-candidate-{run_id}"
  pilot_workflow=macos-pilot.yml
fi

if try_source "$selected_workflow" "$selected_artifact"; then
  candidate_usable=true
elif try_source "$pilot_workflow" macos-pilot-archives; then
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
