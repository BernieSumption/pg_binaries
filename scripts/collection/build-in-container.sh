#!/usr/bin/env bash
set -euo pipefail

architecture=${PG_ARCHITECTURE:-x86_64}
case "$architecture:$(uname -m)" in
  x86_64:x86_64|arm64:aarch64) ;;
  *) echo "Build container architecture does not match $architecture: $(uname -m)" >&2; exit 2 ;;
esac
pg_version=18.6
core_archive="postgresql-${pg_version}-linux-${architecture}.tar.gz"
cd /input
sha256sum -c "$core_archive.sha256"
mkdir -p /work/core /work/source /work/stage /out
tar -xzf "$core_archive" -C /work/core
mv /work/core/postgresql /opt/postgresql
pgroot=/opt/postgresql
test "$("$pgroot/bin/pg_config" --version)" = "PostgreSQL $pg_version"

build_one() {
  version=$1
  sha256=$2
  source_url="https://github.com/aws/pgcollection/archive/refs/tags/v${version}.tar.gz"
  source_archive="pgcollection-v${version}.tar.gz"
  archive="collection-${version}-postgresql-${pg_version}-linux-${architecture}.tar.gz"
  source_dir="/work/source/${version}"
  stage_root="/work/stage/${version}"
  package_root="/work/package/${version}"
  mkdir -p "$source_dir" "$stage_root" "$package_root"
  curl -fL --retry 3 -o "/work/source/$source_archive" "$source_url"
  printf '%s  %s\n' "$sha256" "/work/source/$source_archive" | sha256sum -c -
  cp "/work/source/$source_archive" "/out/pgcollection-${version}-source.tar.gz"
  printf '%s  %s\n' "$sha256" "pgcollection-${version}-source.tar.gz" > "/out/pgcollection-${version}-source.tar.gz.sha256"
  tar -xzf "/work/source/$source_archive" -C "$source_dir"
  source_root="$source_dir/pgcollection-${version}"
  test -f "$source_root/Makefile"
  test -f "$source_root/LICENSE"
  test -f "$source_root/collection.control.in" || test -f "$source_root/collection.control"
  test "$(sed -n 's/^EXTVERSION = //p' "$source_root/Makefile")" = "$version"
  make -C "$source_root" PG_CONFIG="$pgroot/bin/pg_config" -j 4
  make -C "$source_root" PG_CONFIG="$pgroot/bin/pg_config" install DESTDIR="$stage_root"
  prefix=$("$pgroot/bin/pg_config" --prefix)
  install_root="$stage_root$prefix"
  mkdir -p "$package_root/collection/lib" "$package_root/collection/share/extension" "$package_root/collection/LICENSES"
  test -f "$install_root/lib/collection.so"
  cp "$install_root/lib/collection.so" "$package_root/collection/lib/"
  cp "$install_root/share/extension/collection"* "$package_root/collection/share/extension/"
  cp "$source_root/LICENSE" "$package_root/collection/LICENSES/pgcollection.txt"
  cp "$source_root/NOTICE" "$package_root/collection/LICENSES/pgcollection-NOTICE.txt"
  test -f "$source_root/include/uthash/LICENSE"
  cp "$source_root/include/uthash/LICENSE" "$package_root/collection/LICENSES/uthash.txt"
  cp "$source_root/NOTICE" "/out/pgcollection-${version}-NOTICE.txt"
  cp "$source_root/LICENSE" "/out/pgcollection-${version}-LICENSE.txt"
  cp "$source_root/include/uthash/LICENSE" "/out/pgcollection-${version}-uthash-LICENSE.txt"
  uthash_sha=$(sha256sum "$source_root/include/uthash/LICENSE" | awk '{print $1}')
  python3 - "$package_root" "$version" "$pg_version" "$architecture" "$source_url" "$sha256" "$uthash_sha" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
version, pg_version, architecture, url, sha256, uthash_sha = sys.argv[2:]
metadata = {
    "project": "collection", "version": version, "sql_names": ["collection"],
    "requires": [], "configuration_prerequisites": [], "runtime_prerequisites": [],
    "postgresql_version": pg_version, "platform": "linux", "architecture": architecture,
    "source": {"url": url, "sha256": sha256},
}
(root / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
components = [{
    "component": "pgcollection", "version": version,
    "payload_paths": ["lib/collection.so", "share/extension"],
    "license_file": "pgcollection.txt", "additional_license_files": ["pgcollection-NOTICE.txt"],
    "license_source": url + "#LICENSE",
    "source_url": url, "source_sha256": sha256,
    "redistribution_review": {
        "status": "resolved",
        "basis": "The exact unmodified upstream source archive supplies the Apache-2.0 project license, retained in this feasibility archive.",
        "source_obligation": "none",
    },
}, {
    "component": "uthash", "version": "vendored by pgcollection",
    "payload_paths": ["lib/collection.so"], "license_file": "uthash.txt",
    "license_source": url + "#include/uthash/LICENSE", "source_url": url,
    "source_sha256": sha256, "license_sha256": uthash_sha,
    "redistribution_review": {
        "status": "resolved",
        "basis": "The unmodified upstream archive identifies and supplies the uthash license; its copyright, conditions and disclaimer are retained in this archive.",
        "source_obligation": "none",
    },
}]
(root / "collection/LICENSES/collection-inventory.json").write_text(
    json.dumps({"schema_version": 1, "components": components}, indent=2, sort_keys=True) + "\n")
PY
  (cd "$package_root" && tar -czf "/out/$archive" collection metadata.json)
  (cd /out && sha256sum "$archive" > "$archive.sha256")
  printf '%s  %s\n' "$uthash_sha" "pgcollection-${version}-uthash-LICENSE.txt" > "/out/pgcollection-${version}-uthash-LICENSE.txt.sha256"
}

# Digests were independently obtained from the exact public GitHub tag archive URLs.
build_one 1.1.1 ab99a969334442e4a3c77405bc9ffed0083595d18f3898d64a731353a32bec5e
build_one 2.1.3 a6b07864e5893d3b682bb3223fd6d33015709765c9d40d415c85112358f0e3e4
