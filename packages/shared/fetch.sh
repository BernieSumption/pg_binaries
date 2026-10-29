#!/usr/bin/env bash
set -euo pipefail

[[ $# == 3 ]] || { echo "usage: $0 URL SHA256 DESTINATION" >&2; exit 2; }
url=$1 expected=$2 destination=$3
[[ $expected =~ ^[0-9a-f]{64}$ ]] || { echo 'Invalid source SHA-256' >&2; exit 2; }
mkdir -p "$(dirname "$destination")"
curl --fail --location --retry 3 --silent --show-error "$url" --output "$destination"
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$destination" | awk '{print $1}')
else
  actual=$(shasum -a 256 "$destination" | awk '{print $1}')
fi
[[ $actual == "$expected" ]] || { echo "Source checksum mismatch: $destination" >&2; exit 1; }
