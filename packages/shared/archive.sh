#!/usr/bin/env bash
set -euo pipefail

[[ $# == 2 ]] || { echo "usage: $0 PAYLOAD_DIRECTORY OUTPUT_ARCHIVE" >&2; exit 2; }
payload=$1 archive=$2
[[ -d $payload/postgresql ]] || { echo 'Missing postgresql/ archive root' >&2; exit 1; }
mkdir -p "$(dirname "$archive")"
find "$payload/postgresql" -type d -exec chmod 755 {} +
printf '%s\n' 'See https://github.com/BernieSumption/pg_binaries/blob/main/LICENSES.md' > "$payload/postgresql/LICENCE"
chmod 644 "$payload/postgresql/LICENCE"
export COPYFILE_DISABLE=1
tar -C "$payload" -czf "$archive" postgresql
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$archive" > "$archive.sha256"
else
  shasum -a 256 "$archive" > "$archive.sha256"
fi
echo "$archive"
