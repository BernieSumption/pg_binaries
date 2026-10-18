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
python3 "$repo/tools/actions_candidate_discovery.py" \
  --repository "$GITHUB_REPOSITORY" \
  --workflow macos-arm64-pilot.yml \
  --branch "$GITHUB_REF_NAME" \
  --current-run-id "$GITHUB_RUN_ID" \
  --artifact-name-template macos-arm64-pilot-archives \
  --archive-basename "$core_name" \
  --project postgresql --version "$version" --platform macos-arm64 \
  --postgresql-version "$version" \
  --output-directory "$output" \
  --manifest-path "$candidate_manifest"

read -r candidate_run_id candidate_head_sha < <(python3 - "$candidate_manifest" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))["archives"]
if len(rows) > 1:
    raise SystemExit("candidate discovery returned more than one core archive")
if rows:
    print(rows[0]["source"]["run_id"], rows[0]["source"]["head_sha"])
else:
    print("none none")
PY
)

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
if [[ $candidate_run_id != none ]]; then
  if python3 "$repo/tools/macos_core_target_config.py" \
      --base-target "$base_target" --core-archive "$output/$core_name" \
      --source-run-id "$candidate_run_id" --output "$target"; then
    source_revision=$(python3 - "$target" <<'PY'
import json
import sys

print(json.load(open(sys.argv[1], encoding="utf-8"))["core_archive"]["source_revision"])
PY
)
    if [[ $source_revision == "$candidate_head_sha" ]]; then
      if git -C "$repo" cat-file -e "$source_revision^{commit}" 2>/dev/null \
          || git -C "$repo" fetch --no-tags --depth=1 origin "$source_revision"; then
        if git -C "$repo" diff --quiet "$source_revision" HEAD -- \
            scripts/macos/build.sh scripts/macos/build-source-dependencies.sh \
            scripts/macos/bundle.py scripts/macos/licenses.py \
            tools/source_archive.py tools/discover_builtins.py \
            tools/create_macos_symbols.py \
            && check_source_archive; then
          candidate_usable=true
        fi
      fi
    fi
  fi
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
