#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-build-selected.sh CORE_ARCHIVES OUTPUT_DIRECTORY TARGET_CONFIG}
output=${2:?output directory required}
target_config=${3:?resolved target config required}
repo=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)
source "$repo/scripts/macos/core-prefix.sh"
selection=$(python3 - "$target_config" <<'PY'
import json, sys
target=json.load(open(sys.argv[1], encoding="utf-8"))
core=target.get("core_archive", {})
if target.get("postgresql_version") != "17.11" or target.get("extension_version") != "3.7.0":
    raise SystemExit("only selected Address Standardizer 3.7.0 / PostgreSQL 17.11 is enabled")
if target.get("architecture") not in {"arm64", "x86_64"}:
    raise SystemExit("unsupported macOS architecture")
if core.get("basename") != f"postgresql-17.11-macos-{target['architecture']}.tar.gz":
    raise SystemExit("resolved core archive identity mismatch")
for key in ("sha256", "build_id", "source_revision"):
    if not core.get(key): raise SystemExit(f"resolved core lacks {key}")
print("17.11", target["architecture"], core["basename"], core["sha256"], core["build_id"], core["source_revision"])
PY
)
read -r pg_version architecture core_name core_sha core_build_id core_revision <<< "$selection"
core_archives=$(cd "$core_archives" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)
if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "Build requires native macOS $architecture" >&2; exit 1
fi
core_archive="$core_archives/$core_name"
test -s "$core_archive" && (cd "$core_archives" && shasum -a 256 -c "$core_name.sha256")
printf '%s  %s\n' "$core_sha" "$core_archive" | shasum -a 256 -c -
work=$(mktemp -d /tmp/address-standardizer-macos-build.XXXXXX)
prefix_link_created=false
cleanup() { macos_remove_core_prefix; rm -rf "$work"; }
trap cleanup EXIT
mkdir -p "$work/core" "$work/source" "$work/stage" "$work/package" "$work/pcre2"
tar -xzf "$core_archive" -C "$work/core"
pgroot=$(cd "$work/core/postgresql" && pwd -P)
prefix=$(macos_core_prefix_from_archive "$pgroot" "$pg_version" "$architecture" "$core_build_id" "$core_revision")
macos_restore_core_prefix "$prefix" "$pgroot"
prefix_link_created=true
pg_config="$prefix/bin/pg_config"
test "$("$pg_config" --version)" = "PostgreSQL $pg_version"
export MACOSX_DEPLOYMENT_TARGET=11.0
pcre_version=10.48
pcre_sha=b6c68fdf6f3ac31388b50aa89ff0fc49c00c987c16e7b5146491d12003f2c8ed
cd "$work/source"
curl -fL --retry 3 -o "pcre2-$pcre_version.tar.bz2" "https://github.com/PCRE2Project/pcre2/releases/download/pcre2-$pcre_version/pcre2-$pcre_version.tar.bz2"
printf '%s  %s\n' "$pcre_sha" "pcre2-$pcre_version.tar.bz2" | shasum -a 256 -c -
tar -xjf "pcre2-$pcre_version.tar.bz2"
cd "pcre2-$pcre_version"
./configure --prefix="$work/pcre2" --enable-shared --disable-static --disable-pcre2-16 --disable-pcre2-32 --enable-jit
make -s -j"$(sysctl -n hw.ncpu)"
make -s install
cd "$work/source"
git init -q address_standardizer
git -C address_standardizer remote add origin https://github.com/postgis/address_standardizer.git
git -C address_standardizer fetch --depth 1 origin refs/tags/v3.7.0
git -C address_standardizer checkout --detach FETCH_HEAD
expected_commit=fa11ff53eb49b863d9ffff37f6afd5ff9299c581
test "$(git -C address_standardizer rev-parse HEAD)" = "$expected_commit"
cd address_standardizer
for control in address_standardizer.control address_standardizer_data_us.control; do
  test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" "$control")" = 3.7
done
make -s PG_CONFIG="$pg_config" PG_CPPFLAGS="-I$work/pcre2/include -DAS_VERSION=\\\"3.7\\\" -DPCRE_VERSION=2" PG_LDFLAGS="-L$work/pcre2/lib" -j"$(sysctl -n hw.ncpu)"
make -s PG_CONFIG="$pg_config" PG_CPPFLAGS="-I$work/pcre2/include -DAS_VERSION=\\\"3.7\\\" -DPCRE_VERSION=2" PG_LDFLAGS="-L$work/pcre2/lib" install DESTDIR="$work/stage"
pkglib_rel=$(python3 - "$pg_config" "$pgroot" <<'PY'
from pathlib import Path
import sys
import subprocess
pg_config=sys.argv[1]
root=Path(sys.argv[2]).resolve()
pkglib=Path(subprocess.check_output([pg_config, "--pkglibdir"], text=True).strip())
sharedir=Path(subprocess.check_output([pg_config, "--sharedir"], text=True).strip())
pkglib=pkglib.resolve()
sharedir=sharedir.resolve()
if not pkglib.is_relative_to(root) or not sharedir.is_relative_to(root):
    raise SystemExit("selected PostgreSQL install directories are outside the extracted core")
print(pkglib.relative_to(root), sharedir.relative_to(root), sep="\t")
PY
)
read -r pkglib_rel sharedir_rel <<< "$pkglib_rel"
stage_root="$work/stage$pgroot"
if [[ ! -s "$stage_root/$pkglib_rel/address_standardizer.dylib" || ! -s "$stage_root/$sharedir_rel/extension/address_standardizer.control" ]]; then
  printf 'Expected staged library: %s\n' "$stage_root/$pkglib_rel/address_standardizer.dylib" >&2
  printf 'Expected staged control: %s\n' "$stage_root/$sharedir_rel/extension/address_standardizer.control" >&2
  printf 'Actual staged Address Standardizer files:\n' >&2
  find "$work/stage" -type f -name '*address_standardizer*' -print | sort >&2
  exit 1
fi
pkg="$work/package/address_standardizer"
mkdir -p "$pkg/$pkglib_rel" "$pkg/share/extension" "$pkg/lib" "$pkg/LICENSES"
cp "$stage_root/$pkglib_rel/address_standardizer.dylib" "$pkg/$pkglib_rel/"
cp "$stage_root/$sharedir_rel/extension/address_standardizer"* "$pkg/share/extension/"
cp -a "$work/pcre2/lib"/libpcre2-8*.dylib "$pkg/lib/"
for dependency in "$pkg/lib"/libpcre2-8*.dylib; do
  install_name_tool -id "@loader_path/$(basename "$dependency")" "$dependency"
done
module="$pkg/$pkglib_rel/address_standardizer.dylib"
pcre_load=$(otool -L "$module" | awk '/libpcre2-8.*dylib/ {print $1; exit}')
pcre_dylib=$(find "$pkg/lib" -maxdepth 1 -name 'libpcre2-8*.dylib' -print -quit)
pcre_name=$(basename "$pcre_dylib")
test -n "$pcre_load" && test -n "$pcre_name"
install_name_tool -change "$pcre_load" "@loader_path/$pcre_name" "$module"
cp "$work/source/address_standardizer/COPYING" "$pkg/LICENSES/Address-Standardizer.txt"
cp "$work/source/pcre2-$pcre_version/COPYING" "$pkg/LICENSES/PCRE2.txt"
cat > "$pkg/LICENSES/license-inventory.json" <<EOF
{"schema_version":1,"components":[{"component":"Address Standardizer","version":"3.7.0","payload_paths":["$pkglib_rel/address_standardizer.dylib","share/extension"],"license_file":"Address-Standardizer.txt","license_source":"https://github.com/postgis/address_standardizer/blob/v3.7.0/COPYING","source_commit":"$expected_commit","redistribution_review":{"status":"pending","basis":"Upstream licence is retained; distribution review remains pending.","source_obligation":"none identified"}},{"component":"PCRE2","version":"$pcre_version","payload_paths":["lib"],"license_file":"PCRE2.txt","license_source":"https://github.com/PCRE2Project/pcre2/tree/pcre2-$pcre_version","source_sha256":"$pcre_sha","redistribution_review":{"status":"pending","basis":"Upstream licence is retained; distribution review remains pending.","source_obligation":"none identified"}}]}
EOF
cat > "$work/package/metadata.json" <<EOF
{"project":"Address Standardizer","version":"3.7.0","sql_names":["address_standardizer","address_standardizer_data_us"],"requires":[],"configuration_prerequisites":[],"runtime_prerequisites":[],"postgresql_version":"$pg_version","platform":"macos","architecture":"$architecture","source":{"url":"https://github.com/postgis/address_standardizer/tree/v3.7.0","commit":"$expected_commit"},"core_archive":{"basename":"$core_name","sha256":"$core_sha"},"dependencies":[{"name":"PCRE2","version":"$pcre_version","sha256":"$pcre_sha"}],"license_inventory":"address_standardizer/LICENSES/license-inventory.json"}
EOF
cp "$pkg/$pkglib_rel/address_standardizer.dylib" "$pgroot/$pkglib_rel/"
cp -a "$pkg/share/extension/." "$pgroot/share/extension/"
name="address-standardizer-3.7.0-postgresql-$pg_version-macos-$architecture.tar.gz"
tar -C "$work/package" -czf "$output/$name" address_standardizer metadata.json
cd "$output"
shasum -a 256 "$name" > "$name.sha256"
cat > build-evidence.txt <<EOF
address_standardizer_source_commit=$expected_commit
pcre2_source_sha256=$pcre_sha
postgresql_version=$pg_version
architecture=$architecture
EOF
