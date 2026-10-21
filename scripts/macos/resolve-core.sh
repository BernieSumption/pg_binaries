#!/usr/bin/env bash
set -euo pipefail

base_target=${1:?usage: resolve-core.sh BASE_TARGET OUTPUT_DIRECTORY}
output=${2:?usage: resolve-core.sh BASE_TARGET OUTPUT_DIRECTORY}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)

: "${GITHUB_REPOSITORY:?required for Actions core provenance}"
: "${GITHUB_REF_NAME:?required for Actions core provenance}"
: "${GITHUB_RUN_ID:?required for Actions core provenance}"
: "${GITHUB_RUN_ATTEMPT:?required for Actions core provenance}"

selection=$(python3 - "$base_target" <<'PY'
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
read -r version architecture core_name <<< "$selection"

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

if pin_output=$(python3 "$repo/tools/macos_core_pin.py" "$version" "$architecture"); then
  for field in workflow run_id artifact_name archive_name sha256; do
    value=$(printf '%s\n' "$pin_output" | sed -n "s/^${field}=//p")
    [[ -n $value ]] || { echo "macOS core pin omitted $field" >&2; exit 1; }
    case "$field" in
      workflow) pin_workflow=$value ;;
      run_id) pin_run_id=$value ;;
      artifact_name) pin_artifact_name=$value ;;
      archive_name) pin_archive_name=$value ;;
      sha256) pin_sha256=$value ;;
    esac
  done
  rm -f "$output/$core_name" "$output/$core_name.sha256" "$target"
  if gh run download "$pin_run_id" --name "$pin_artifact_name" --dir "$output"; then
    [[ -f "$output/$pin_archive_name" ]] || {
      echo "pinned macOS core artifact lacks $pin_archive_name" >&2
      exit 1
    }
    actual_sha256=$(shasum -a 256 "$output/$core_name" | awk '{print $1}')
    [[ $actual_sha256 == "$pin_sha256" ]] || {
      echo "pinned macOS core archive checksum differs" >&2
      exit 1
    }
    builder_provenance=$(python3 - "$output/$core_name" "$pin_run_id" <<'PY'
import json
import re
import sys
import tarfile

with tarfile.open(sys.argv[1], "r:gz") as archive:
    members = archive.getmembers()
    if len(members) > 100_000 or len({member.name for member in members}) != len(members):
        raise SystemExit("core archive has too many or duplicate entries")
    matches = [member for member in members if member.name == "postgresql/manifest.json"]
    if len(matches) != 1 or not matches[0].isfile() or matches[0].size > 1024 * 1024:
        raise SystemExit("core archive must contain one bounded regular manifest")
    manifest = json.loads(archive.extractfile(matches[0]).read(1024 * 1024 + 1))
build_id = manifest.get("build_id") if isinstance(manifest, dict) else None
revision = manifest.get("source_revision") if isinstance(manifest, dict) else None
match = re.fullmatch(rf"github-{sys.argv[2]}-([1-9][0-9]*)", build_id or "")
if not match or not re.fullmatch(r"[0-9a-f]{40}", revision or ""):
    raise SystemExit("pinned core archive has invalid builder provenance")
print(match.group(1), revision)
PY
)
    read -r builder_attempt source_revision <<< "$builder_provenance"
    builder_json=$(gh api "repos/$GITHUB_REPOSITORY/actions/runs/$pin_run_id")
    python3 - "$builder_json" "$GITHUB_REPOSITORY" "$GITHUB_REF_NAME" \
      "$pin_run_id" "$builder_attempt" "$source_revision" "$architecture" "$pin_workflow" <<'PY'
import json
import re
import sys

run = json.loads(sys.argv[1])
repository, branch, run_id, attempt, revision, architecture, workflow = sys.argv[2:]
suffix = "arm64" if architecture == "arm64" else "x86_64"
pilot = f"macos-{suffix}-pilot.yml" if architecture == "arm64" else "macos-pilot.yml"
allowed = {
    pilot,
    "postgresql-macos-selected-publication.yml",
    f"hypopg-macos-{suffix}-selected-publication.yml",
    "pg-jsonschema-macos-changed-profiles.yml",
    "pg-jsonschema-macos-selected-publication.yml",
}
if architecture == "arm64":
    allowed.add("pgtap-macos-arm64-selected-publication.yml")
repo = run.get("repository") if isinstance(run, dict) else None
head_repo = run.get("head_repository") if isinstance(run, dict) else None
run_workflow = str(run.get("path", "")).split("@", 1)[0].rsplit("/", 1)[-1]
workflow_matches = (run_workflow == workflow or
                    (workflow == "postgresql-macos-selected-publication.yml" and
                     run_workflow == "selected-extension-publication.yml"))
valid = (workflow in allowed
         and isinstance(repo, dict) and str(repo.get("full_name", "")).casefold() == repository.casefold()
         and isinstance(head_repo, dict) and str(head_repo.get("full_name", "")).casefold() == repository.casefold()
         and str(run.get("id")) == run_id
         and isinstance(run.get("run_attempt"), int) and not isinstance(run.get("run_attempt"), bool)
         and run.get("run_attempt") == int(attempt)
         and run.get("head_branch") == branch and run.get("event") in {"push", "workflow_dispatch"}
         and run.get("status") == "completed" and run.get("conclusion") == "success"
         and workflow_matches
         and run.get("head_sha") == revision and re.fullmatch(r"[0-9a-f]{40}", revision) is not None)
if not valid:
    raise SystemExit("pinned macOS core builder run does not match its archive")
PY
    python3 "$repo/tools/macos_core_target_config.py" \
      --base-target "$base_target" --core-archive "$output/$core_name" \
      --source-run-id "$pin_run_id" --source-run-attempt "$builder_attempt" \
      --output "$target"
    if ! git -C "$repo" cat-file -e "$source_revision^{commit}" 2>/dev/null \
        && ! git -C "$repo" fetch --no-tags --depth=1 origin "$source_revision"; then
      echo "cannot inspect pinned macOS core builder revision" >&2
      exit 1
    fi
    git -C "$repo" diff --quiet "$source_revision" HEAD -- \
      scripts/macos/build.sh scripts/macos/build-source-dependencies.sh \
      scripts/macos/bundle.py tools/license_pointer.py \
      tools/source_archive.py tools/discover_builtins.py \
      tools/create_macos_symbols.py || {
        echo "pinned macOS core build inputs changed" >&2
        exit 1
      }
    check_source_archive
    echo "Reusing pinned PostgreSQL $version core from Actions run $pin_run_id"
    exit 0
  fi
  echo "Pinned macOS core artifact is unavailable; building PostgreSQL $version on this runner"
else
  pin_status=$?
  [[ $pin_status -eq 3 ]] || exit "$pin_status"
  echo "No unpublished macOS core pin; building PostgreSQL $version on this runner"
fi

rm -f "$output/$core_name" "$output/$core_name.sha256" "$target"
bash "$repo/scripts/macos/build.sh" "$output" "$architecture" "$version" core-only
python3 "$repo/tools/macos_core_target_config.py" \
  --base-target "$base_target" --core-archive "$output/$core_name" \
  --source-run-id "$GITHUB_RUN_ID" --source-run-attempt "$GITHUB_RUN_ATTEMPT" \
  --output "$target"
check_source_archive
