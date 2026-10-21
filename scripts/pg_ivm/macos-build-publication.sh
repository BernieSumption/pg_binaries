#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-build-publication.sh CORE_ARCHIVE_DIRECTORY TARGET_JSON OUTPUT_DIRECTORY}
target_json=${2:?usage: macos-build-publication.sh CORE_ARCHIVE_DIRECTORY TARGET_JSON OUTPUT_DIRECTORY}
output=${3:?usage: macos-build-publication.sh CORE_ARCHIVE_DIRECTORY TARGET_JSON OUTPUT_DIRECTORY}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
core_archives=$(cd "$core_archives" && pwd)
target_json=$(cd "$(dirname "$target_json")" && pwd)/$(basename "$target_json")
mkdir -p "$output"
output=$(cd "$output" && pwd)
read -r pg_version architecture core_name core_sha256 <<<"$(python3 - "$target_json" <<'PY'
import json, re, sys
from pathlib import Path
t = json.loads(Path(sys.argv[1]).read_text())
version, arch = t.get("postgresql_version"), t.get("architecture")
if version not in {"15.19", "16.15", "17.11", "18.6"} or arch not in {"arm64", "x86_64"} or t.get("platform") != f"macos-{arch}":
    raise SystemExit("unsupported pg_ivm macOS target")
core = t.get("core_archive")
if not isinstance(core, dict) or core.get("basename") != f"postgresql-{version}-macos-{arch}.tar.gz":
    raise SystemExit("resolved target has a mismatched PostgreSQL core archive")
if not re.fullmatch(r"[0-9a-f]{64}", str(core.get("sha256", ""))):
    raise SystemExit("resolved target must bind the core archive SHA-256")
print(version, arch, core["basename"], core["sha256"])
PY
)"
extension_version=1.16
source_url='https://github.com/sraoss/pg_ivm/archive/refs/tags/v1.16.tar.gz'
source_sha256=87807d6af1974fce591715d55f75d939dffea33ea6908b413e62d3dd79b9c583
extension_name="pg_ivm-${extension_version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This publication build requires native macOS $architecture" >&2; exit 1
fi
test -s "$core_archives/$core_name" && test -s "$core_archives/$core_name.sha256"
(cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha256" "$core_name" | (cd "$core_archives" && shasum -a 256 -c -)
work=$(mktemp -d /tmp/pgivm-macos.XXXXXX)
prefix_link_created=false
cleanup() {
  if [[ $prefix_link_created == true && -L ${prefix_link:-} ]]; then rm "$prefix_link"; fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/core" "$work/source" "$work/stage" "$work/package/pg_ivm"/{lib,share/extension,bin}
tar -xzf "$core_archives/$core_name" -C "$work/core"
pgroot="$work/core/postgresql"
test -s "$pgroot/include/server/pg_config.h" && test -s "$pgroot/lib/pgxs/src/makefiles/pgxs.mk"
read -r core_build_id core_source_revision <<<"$(python3 - "$target_json" <<'PY'
import json,sys
from pathlib import Path
t=json.loads(Path(sys.argv[1]).read_text()); c=t["core_archive"]
print(c.get("build_id", ""), c.get("source_revision", ""))
PY
)"
source "$repo/scripts/macos/core-prefix.sh"
prefix=$(macos_core_prefix_from_archive "$pgroot" "$pg_version" "$architecture" "$core_build_id" "$core_source_revision")
macos_restore_core_prefix "$prefix" "$pgroot"
python3 - "$pgroot" "$target_json" <<'PY'
import json, pathlib, sys
root=pathlib.Path(sys.argv[1]); target=json.loads(pathlib.Path(sys.argv[2]).read_text())
m=json.loads((root/'manifest.json').read_text())
expected={"component":"postgresql","version":target["postgresql_version"],"postgresql_version":target["postgresql_version"],"platform":"macos","architecture":target["architecture"]}
if any(m.get(k)!=v for k,v in expected.items()): raise SystemExit("resolved core archive manifest does not match selected target")
PY
pg_config="$prefix/bin/pg_config"
test "$("$pg_config" --version)" = "PostgreSQL $pg_version"
export MACOSX_DEPLOYMENT_TARGET=11.0
cd "$work/source"
curl -fL --retry 3 -o pg_ivm.tar.gz "$source_url"
printf '%s  %s\n' "$source_sha256" pg_ivm.tar.gz | shasum -a 256 -c -
test "$(tar -tzf pg_ivm.tar.gz | cut -d/ -f1 | sort -u)" = pg_ivm-1.16
tar -xzf pg_ivm.tar.gz
cd pg_ivm-1.16
test "$(sed -n "s/^default_version = '\\([^']*\\)'/\\1/p" pg_ivm.control)" = "$extension_version"
test "$(sed -n 's/^schema = \([^ ]*\)/\1/p' pg_ivm.control)" = pg_catalog
make PG_CONFIG="$pg_config" -j "$(sysctl -n hw.ncpu)"
make PG_CONFIG="$pg_config" install DESTDIR="$work/stage"
staged_root="$work/stage$(cd "$pgroot" && pwd -P)"
native_module=$(find "$staged_root/lib" -maxdepth 1 -type f \( -name pg_ivm.dylib -o -name pg_ivm.so \) -print)
test "$(printf '%s\n' "$native_module" | wc -l | tr -d ' ')" = 1
native_name=$(basename "$native_module")
cp "$native_module" "$work/package/pg_ivm/lib/"
cp "$staged_root/share/extension/"* "$work/package/pg_ivm/share/extension/"
cp "$staged_root/bin/pg_ivm_dump_metadata" "$work/package/pg_ivm/bin/"
python3 "$repo/tools/license_pointer.py" write "$work/package/pg_ivm" pg_ivm
cat > "$work/package/metadata.json" <<EOF
{"project":"pg_ivm","version":"$extension_version","sql_names":["pg_ivm"],"requires":[],"configuration_prerequisites":[{"type":"postgresql_setting","name":"shared_preload_libraries","value":"pg_ivm"}],"runtime_prerequisites":[],"postgresql_version":"$pg_version","platform":"macos","architecture":"$architecture","source":{"url":"$source_url","sha256":"$source_sha256"},"core_archive":{"basename":"$core_name","sha256":"$core_sha256"}}
EOF
tar -C "$work/package" -czf "$output/$extension_name" pg_ivm metadata.json
python3 "$repo/tools/license_pointer.py" verify "$output/$extension_name" pg_ivm
(cd "$output" && shasum -a 256 "$extension_name" > "$extension_name.sha256" && shasum -a 256 -c "$extension_name.sha256")
echo "PASS: built pg_ivm $extension_version against selected PostgreSQL $pg_version on macOS $architecture"
