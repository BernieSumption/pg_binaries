#!/usr/bin/env bash
set -euo pipefail
[[ $# == 1 ]] || { echo "usage: $0 PACKAGE" >&2; exit 2; }
[[ $(uname -s) == Darwin ]] || { echo 'macOS build requires macOS' >&2; exit 1; }
for tool in python3 curl make clang tar; do
  command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
