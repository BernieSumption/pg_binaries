macos_core_prefix_from_archive() {
  local pgroot=$1 pg_version=$2 architecture=$3 core_build_id=$4 core_source_revision=$5
  python3 - "$pgroot" "$pg_version" "$architecture" "$core_build_id" "$core_source_revision" <<'PY'
import json
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
pg_version, architecture, build_id, source_revision = sys.argv[2:]
manifest = json.loads((root / "manifest.json").read_text())
expected = {
    "component": "postgresql", "version": pg_version, "postgresql_version": pg_version,
    "platform": "macos", "architecture": architecture, "build_id": build_id,
    "source_revision": source_revision,
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
}

macos_restore_core_prefix() {
  local prefix=$1 pgroot=$2
  if [[ -e "$prefix" || -L "$prefix" ]]; then
    echo "Refusing to replace existing PostgreSQL prefix path: $prefix" >&2
    return 1
  fi
  mkdir -p "$(dirname "$prefix")"
  ln -s "$pgroot" "$prefix"
  prefix_link=$prefix
  prefix_link_created=true
}

macos_remove_core_prefix() {
  if [[ ${prefix_link_created:-false} == true && -n ${prefix_link:-} && -L $prefix_link ]]; then
    rm "$prefix_link"
  fi
}
