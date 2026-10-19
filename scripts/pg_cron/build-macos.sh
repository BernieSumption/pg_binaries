#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: build-macos.sh CORE_ARCHIVE_DIRECTORY TARGET_JSON OUTPUT_DIRECTORY}
target_config=${2:?usage: build-macos.sh CORE_ARCHIVE_DIRECTORY TARGET_JSON OUTPUT_DIRECTORY}
output=${3:?usage: build-macos.sh CORE_ARCHIVE_DIRECTORY TARGET_JSON OUTPUT_DIRECTORY}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
target_values=$(python3 "$repo/scripts/pg_cron/macos_target.py" --require-resolved "$target_config")
IFS=$'\t' read -r pg_version architecture platform core_name core_sha256 core_build_id \
  core_source_revision source_url source_sha256 extension_name <<< "$target_values"

if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This build requires native macOS $architecture" >&2
  exit 1
fi
core_archives=$(cd "$core_archives" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
test -s "$core_archives/$core_name" && test -s "$core_archives/$core_name.sha256"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_archives" && shasum -a 256 -c -)

work=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/pgcron-macos-build.XXXXXX")
prefix_link_created=false
source "$repo/scripts/macos/core-prefix.sh"
cleanup() {
  macos_remove_core_prefix
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/core" "$work/source" "$work/stage" "$work/package"
tar -xzf "$core_archives/$core_name" -C "$work/core"
pgroot="$work/core/postgresql"
test -s "$pgroot/include/server/pg_config.h"
test -s "$pgroot/lib/pgxs/src/makefiles/pgxs.mk"
prefix=$(macos_core_prefix_from_archive "$pgroot" "$pg_version" "$architecture" \
  "$core_build_id" "$core_source_revision")
macos_restore_core_prefix "$prefix" "$pgroot"
pg_config="$prefix/bin/pg_config"
test "$("$pg_config" --version)" = "PostgreSQL $pg_version"
export MACOSX_DEPLOYMENT_TARGET=11.0

cd "$work/source"
curl -fL --retry 3 -o pg_cron.tar.gz "$source_url"
printf '%s  %s\n' "$source_sha256" pg_cron.tar.gz | shasum -a 256 -c -
test "$(tar -tzf pg_cron.tar.gz | cut -d/ -f1 | sort -u)" = pg_cron-1.6.8
tar -xzf pg_cron.tar.gz
cd pg_cron-1.6.8
test "$(sed -n "s/^default_version = '\\([^']*\\)'/\\1/p" pg_cron.control)" = 1.6
make PG_CONFIG="$pg_config" PG_LDFLAGS='-Wl,-rpath,@loader_path' -j "$(sysctl -n hw.ncpu)"
make PG_CONFIG="$pg_config" install DESTDIR="$work/stage"
staged_root="$work/stage$(cd "$pgroot" && pwd -P)"
mkdir -p "$work/package/pg_cron"/{lib,share/extension,LICENSES}
modules=()
for module in "$staged_root/lib/pg_cron.dylib" "$staged_root/lib/pg_cron.so"; do
  [[ ! -f "$module" ]] || modules+=("$module")
done
if [[ ${#modules[@]} != 1 ]]; then
  echo "Expected exactly one staged pg_cron PGXS module, found ${#modules[@]}" >&2
  exit 1
fi
module_name=${modules[0]##*/}
cp "${modules[0]}" "$work/package/pg_cron/lib/"
cp "$staged_root/share/extension/"pg_cron* "$work/package/pg_cron/share/extension/"
cp LICENSE "$work/package/pg_cron/LICENSES/pg_cron.txt"
python3 - "$work/package/pg_cron/LICENSES/pg_cron-inventory.json" "$source_url" "$source_sha256" "$module_name" <<'PY'
import json
import pathlib
import sys
path, url, digest, module = sys.argv[1:]
value = {"schema_version": 1, "components": [{
    "component": "pg_cron", "version": "1.6.8",
    "payload_paths": [f"lib/{module}", "share/extension"],
    "license_file": "pg_cron.txt",
    "license_source": "https://github.com/citusdata/pg_cron/blob/v1.6.8/LICENSE",
    "source_url": url, "source_sha256": digest,
    "redistribution_review": {"status": "resolved",
        "basis": "The unmodified pg_cron 1.6.8 source archive includes the PostgreSQL License for this project. It permits binary redistribution with its copyright notice, permission paragraph and disclaimer retained; this archive includes the complete upstream LICENSE text.",
        "source_obligation": "none"}}]}
pathlib.Path(path).write_text(json.dumps(value, separators=(",", ":")) + "\n")
PY
cat > "$work/package/metadata.json" <<EOF
{"project":"pg_cron","version":"1.6.8","sql_names":["pg_cron"],"requires":[],"configuration_prerequisites":[{"type":"postgresql_setting","name":"shared_preload_libraries","value":"pg_cron"},{"type":"postgresql_setting","name":"cron.use_background_workers","value":"on"}],"runtime_prerequisites":[],"postgresql_version":"$pg_version","platform":"macos","architecture":"$architecture","source":{"url":"$source_url","sha256":"$source_sha256"},"core_archive":{"basename":"$core_name","sha256":"$core_sha256"}}
EOF
grep -Fq 'Permission to use, copy, modify, and distribute this software' LICENSE
test -s "$work/package/pg_cron/lib/$module_name"
test -s "$work/package/pg_cron/share/extension/pg_cron.control"
tar -C "$work/package" -czf "$output/$extension_name" pg_cron metadata.json
(cd "$output" && shasum -a 256 "$extension_name" > "$extension_name.sha256" && shasum -a 256 -c "$extension_name.sha256")
python3 "$repo/tools/check_extension_redistribution.py" "$output/$extension_name"
echo "PASS: built pg_cron 1.6.8 archive for PostgreSQL $pg_version on macOS $architecture"
