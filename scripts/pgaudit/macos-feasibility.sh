#!/usr/bin/env bash
set -euo pipefail

core_archives=${1:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY [17.11|18.6]}
output=${2:?usage: macos-feasibility.sh CORE_ARCHIVE_DIRECTORY OUTPUT_DIRECTORY [17.11|18.6]}
pg_version=${3:-18.6}
architecture=arm64
openssl_url='https://github.com/openssl/openssl/releases/download/openssl-3.5.8/openssl-3.5.8.tar.gz'
openssl_sha256=a8f84a39918ec6415ce765d9b429d313ba97b8143169c172e734b9514464f5b2
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
IFS=$'\t' read -r pgaudit_version core_sha256 core_build_id core_source_revision source_url source_sha256 \
  < <(python3 "$repo/tools/pgaudit_macos_targets.py" "$pg_version" --shell)
core_archives=$(cd "$core_archives" && pwd)
mkdir -p "$output"
output=$(cd "$output" && pwd)

if [[ $(uname -s) != Darwin || $(uname -m) != "$architecture" ]]; then
  echo "This feasibility probe requires native macOS $architecture" >&2
  exit 1
fi

core_name="postgresql-${pg_version}-macos-${architecture}.tar.gz"
core_archive="$core_archives/$core_name"
test -s "$core_archive" && test -s "$core_archive.sha256"
cd "$core_archives"
shasum -a 256 -c "$core_name.sha256"
printf '%s  %s\n' "$core_sha256" "$core_name" | shasum -a 256 -c -

work=$(mktemp -d /tmp/pgaudit-macos.XXXXXX)
prefix_link_created=false
dependencies_created=false
cleanup() {
  if [[ -n ${pg_ctl:-} && -n ${data_dir:-} ]]; then
    "$pg_ctl" -D "$data_dir" -m immediate stop >/dev/null 2>&1 || true
  fi
  if [[ $prefix_link_created == true && -n ${prefix_link:-} && -L $prefix_link ]]; then
    rm "$prefix_link"
  fi
  if [[ $dependencies_created == true && -n ${dependencies_root:-} && -d $dependencies_root ]]; then
    rm -rf "$dependencies_root"
  fi
  rm -rf "$work"
}
trap cleanup EXIT
mkdir -p "$work/source" "$work/first" "$work/extension" "$work/moved" "$work/socket"
staged_dsyms="$output/staged-dsyms"
mkdir -p "$staged_dsyms"
ditto "$core_archives/debug-symbols/dSYMs" "$staged_dsyms"
tar -xzf "$core_archive" -C "$work/first"
pgroot="$work/first/postgresql"
test -s "$pgroot/include/server/pg_config.h"
test -s "$pgroot/lib/pgxs/src/makefiles/pgxs.mk"

PG_VERSION="$pg_version" CORE_BUILD_ID="$core_build_id" CORE_SOURCE_REVISION="$core_source_revision" \
python3 - "$pgroot" > "$work/prefix" <<'PY'
import json
import os
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text())
expected = {
    "component": "postgresql",
    "version": os.environ["PG_VERSION"],
    "postgresql_version": os.environ["PG_VERSION"],
    "platform": "macos",
    "architecture": "arm64",
    "build_id": os.environ["CORE_BUILD_ID"],
    "source_revision": os.environ["CORE_SOURCE_REVISION"],
}
for key, value in expected.items():
    if manifest.get(key) != value:
        raise SystemExit(f"core archive manifest mismatch for {key}: {manifest.get(key)!r}")
header = (root / "include/server/pg_config.h").read_text()
match = re.search(r'#define CONFIGURE_ARGS "[^\n]*?--prefix=([^\']+)', header)
if not match:
    raise SystemExit("cannot read the original PostgreSQL installation prefix")
prefix = pathlib.Path(match.group(1))
if not re.fullmatch(r"/Users/runner/work/_temp/pg-macos-pilot\.[A-Za-z0-9]+/install/postgresql", str(prefix)):
    raise SystemExit(f"unexpected original PostgreSQL prefix: {prefix}")
print(prefix)
PY
prefix=$(cat "$work/prefix")
# pg_config and PGXS retain the build prefix. Recreate it as a temporary link to
# the extracted archive so their generated paths resolve without editing source.
prefix_link=$prefix
if [[ -e "$prefix_link" || -L "$prefix_link" ]]; then
  echo "Refusing to replace existing PostgreSQL prefix path: $prefix_link" >&2
  exit 1
fi
mkdir -p "$(dirname "$prefix_link")"
ln -s "$pgroot" "$prefix_link"
prefix_link_created=true
pg_config="$prefix_link/bin/pg_config"
test "$("$pg_config" --version)" = "PostgreSQL $pg_version"
export MACOSX_DEPLOYMENT_TARGET=11.0

cd "$work/source"
curl -fL --retry 3 -o openssl.tar.gz "$openssl_url"
printf '%s  %s\n' "$openssl_sha256" openssl.tar.gz | shasum -a 256 -c -
test "$(tar -tzf openssl.tar.gz | cut -d/ -f1 | sort -u)" = openssl-3.5.8
tar -xzf openssl.tar.gz
openssl_source="$work/source/openssl-3.5.8"
openssl_prefix="$work/openssl-install"
cd "$openssl_source"
./Configure darwin64-arm64-cc no-tests \
  --prefix="$openssl_prefix" --openssldir="$openssl_prefix/ssl" --libdir=lib
make build_generated -j "$(sysctl -n hw.ncpu)"
test -s include/openssl/opensslconf.h
test -s include/openssl/configuration.h
test -s include/openssl/ssl.h

# PostgreSQL's archived build flags retain this runner-local include path.
# Recreate only the pinned OpenSSL public headers needed by PGXS compilation;
# the archive already supplies PostgreSQL's bundled runtime libraries.
dependencies_root="$(dirname "$(dirname "$prefix")")/dependencies"
if [[ -e "$dependencies_root" || -L "$dependencies_root" ]]; then
  echo "Refusing to replace existing PostgreSQL dependency path: $dependencies_root" >&2
  exit 1
fi
mkdir -p "$dependencies_root/include"
dependencies_created=true
cp -R include/openssl "$dependencies_root/include/"

cd "$work/source"
curl -fL --retry 3 -o pgaudit.tar.gz "$source_url"
printf '%s  %s\n' "$source_sha256" pgaudit.tar.gz | shasum -a 256 -c -
source_directory=$(tar -tzf pgaudit.tar.gz | sed -n '1{s,/.*,,;p;}')
test -n "$source_directory"
test "$(tar -tzf pgaudit.tar.gz | cut -d/ -f1 | sort -u | wc -l | tr -d ' ')" = 1
tar -xzf pgaudit.tar.gz
cd "$work/source/$source_directory"
test "$(sed -n "s/^default_version = '\([^']*\)'/\1/p" pgaudit.control)" = "$pgaudit_version"
make USE_PGXS=1 PG_CONFIG="$pg_config" -j "$(sysctl -n hw.ncpu)"
stage="$work/stage"
make USE_PGXS=1 PG_CONFIG="$pg_config" install DESTDIR="$stage"

# PGXS resolves the linked pg_config prefix before applying DESTDIR. Copy only
# pgAudit's installed files into the standalone extension payload.
staged_root="$stage$(cd "$pgroot" && pwd -P)"
package="$work/package"
mkdir -p "$package/pgaudit/lib" "$package/pgaudit/share/extension" "$package/pgaudit/LICENSES"
modules=()
for suffix in dylib so; do
  [[ ! -s "$staged_root/lib/pgaudit.$suffix" ]] || modules+=("$staged_root/lib/pgaudit.$suffix")
done
if [[ ${#modules[@]} -ne 1 ]]; then
  echo "Expected one installed pgAudit module, found ${#modules[@]}" >&2
  exit 1
fi
module_name=$(basename "${modules[0]}")
cp "${modules[0]}" "$package/pgaudit/lib/$module_name"
mkdir -p "$staged_dsyms/pgaudit/lib"
dsymutil "$package/pgaudit/lib/$module_name" \
  -o "$staged_dsyms/pgaudit/lib/$module_name.dSYM"
cp "$staged_root/share/extension/"pgaudit* "$package/pgaudit/share/extension/"
cat LICENSE "$pgroot/LICENSES/PostgreSQL.txt" > "$package/pgaudit/LICENSES/pgAudit.txt"
grep -Fq 'This code is released under the PostgreSQL licence' "$package/pgaudit/LICENSES/pgAudit.txt"
grep -Fq 'Permission to use, copy, modify, and distribute this software' "$package/pgaudit/LICENSES/pgAudit.txt"
cat > "$package/pgaudit/LICENSES/pgaudit-inventory.json" <<EOF
{
  "schema_version": 1,
  "components": [{
    "component": "pgaudit", "version": "$pgaudit_version",
    "payload_paths": ["lib/$module_name", "share/extension"],
    "license_file": "pgAudit.txt",
    "license_source": "https://github.com/pgaudit/pgaudit/tree/$pgaudit_version/LICENSE",
    "source_url": "$source_url", "source_sha256": "$source_sha256",
    "redistribution_review": {
      "status": "resolved",
      "basis": "The unmodified pgAudit $pgaudit_version LICENSE points to the PostgreSQL licence and names the PostgreSQL Global Development Group. This package retains that upstream notice with the full PostgreSQL licence text already included in the selected PostgreSQL $pg_version archive. The licence permits binary redistribution with the notice and terms retained and requires no source delivery.",
      "source_obligation": "none"
    }
  }]
}
EOF
cat > "$package/metadata.json" <<EOF
{"project":"pgaudit","version":"$pgaudit_version","sql_names":["pgaudit"],"requires":[],"configuration_prerequisites":[{"type":"postgresql_setting","name":"shared_preload_libraries","value":"pgaudit"}],"runtime_prerequisites":[],"postgresql_version":"$pg_version","platform":"macos","architecture":"$architecture","source":{"url":"$source_url","sha256":"$source_sha256"},"core_archive":{"basename":"$core_name","sha256":"$core_sha256"}}
EOF

extension_name="pgaudit-${pgaudit_version}-postgresql-${pg_version}-macos-${architecture}.tar.gz"
tar -C "$package" -czf "$output/$extension_name" pgaudit metadata.json
cd "$output"
shasum -a 256 "$extension_name" > "$extension_name.sha256"

# Test only the extracted archive contents after moving the assembled tree.
shasum -a 256 -c "$extension_name.sha256"
python3 "$repo/tools/check_extension_redistribution.py" "$output/$extension_name"
tar -xzf "$output/$extension_name" -C "$work/extension"
python3 - "$work/extension/pgaudit" "$pgroot" <<'PY'
from pathlib import Path
import sys

extension, core = map(Path, sys.argv[1:])
for source in extension.rglob("*"):
    destination = core / source.relative_to(extension)
    if destination.exists() or destination.is_symlink():
        if source.is_dir() and destination.is_dir() and not source.is_symlink() and not destination.is_symlink():
            continue
        raise SystemExit(f"extension payload collision: {source.relative_to(extension)}")
PY
ditto "$work/extension/pgaudit" "$pgroot"
mv "$pgroot" "$work/moved/postgresql"
pgroot="$work/moved/postgresql"
python3 "$repo/scripts/macos/static_analysis.py" "$pgroot" "$architecture" \
  --archive "$core_archive" --archive "$output/$extension_name" \
  --report "$output/static-analysis.json"

data_dir="$work/data"
pg_ctl="$pgroot/bin/pg_ctl"
export DYLD_LIBRARY_PATH= DYLD_FALLBACK_LIBRARY_PATH=
"$pgroot/bin/initdb" -D "$data_dir" --encoding=UTF8 --locale=C --no-instructions >/dev/null
"$pg_ctl" -D "$data_dir" -l "$work/server.log" -o \
  "-k $work/socket -p 55432 -h '' -c shared_preload_libraries=pgaudit -c logging_collector=on -c log_directory=log -c log_filename=pgaudit.log" -w start
"$pgroot/bin/psql" -X -v ON_ERROR_STOP=1 -h "$work/socket" -p 55432 \
  -d postgres -f "$repo/scripts/pgaudit/probe.sql" | tee "$output/probe-output.txt"
log_file="$data_dir/log/pgaudit.log"
test -s "$log_file"
grep -F 'AUDIT: SESSION' "$log_file" > "$output/audit-log-extract.txt"
grep -F 'DDL' "$log_file" | grep -F 'CREATE TABLE public.pgaudit_probe' >> "$output/audit-log-extract.txt"
grep -F 'WRITE' "$log_file" | grep -F 'INSERT INTO public.pgaudit_probe' >> "$output/audit-log-extract.txt"
grep -F 'READ' "$log_file" | grep -F 'SELECT payload FROM public.pgaudit_probe' >> "$output/audit-log-extract.txt"
"$pg_ctl" -D "$data_dir" -m fast -w stop
data_dir=
pg_ctl=
echo "PASS: pgAudit $pgaudit_version built from PostgreSQL $pg_version archive and verified after relocation on macOS $architecture"
