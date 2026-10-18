#!/usr/bin/env bash
set -euo pipefail
out=${1:?usage: builder-packages.sh OUTPUT_PATH}
docker run --rm --platform linux/amd64 --entrypoint dpkg-query \
  pg-binaries-pgvector-separate-linux -W \
  -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Abbrev}\n' \
  | LC_ALL=C sort > "$out"
python3 - "$out" <<'PY'
from pathlib import Path
import sys

rows = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
if not rows:
    raise SystemExit("builder has no installed package inventory")
for row in rows:
    fields = row.split("\t")
    if len(fields) != 4 or not all(fields[:3]) or fields[3].strip() != "ii":
        raise SystemExit(f"builder package inventory has an invalid or uninstalled entry: {row}")
PY
