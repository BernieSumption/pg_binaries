#!/usr/bin/env bash
set -euo pipefail

prefix_arg=${1:?usage: build-dependencies.sh <output-prefix>}
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
support_file="$repo_root/support.json"

for command in python3 curl make clang tar; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command not found: $command" >&2
    exit 1
  fi
done
if [[ $(uname -s) != Darwin || $(uname -m) != arm64 ]]; then
  echo "This builder requires native macOS arm64" >&2
  exit 1
fi

prefix=$(mkdir -p "$prefix_arg" && cd "$prefix_arg" && pwd)
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/pg-macos-dependencies.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
MACOSX_DEPLOYMENT_TARGET=$(python3 - "$support_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    print(json.load(source)["targets"]["macos-arm64"]["minimum_os_version"])
PY
)
export MACOSX_DEPLOYMENT_TARGET
jobs=$(sysctl -n hw.ncpu)

python3 - "$support_file" > "$work_dir/dependencies.tsv" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    dependencies = json.load(source)["postgresql"]["build_inputs"]["macos-arm64"]["dependencies"]
for name in ("openssl", "icu", "lz4", "zstd", "libxml2", "libxslt"):
    item = dependencies[name]
    print("\t".join((name, item["version"], item["url"], item["sha256"])))
PY

while IFS=$'\t' read -r name version url expected; do
  archive="$work_dir/$name"
  source="$work_dir/source-$name"
  echo "Downloading $name $version" >&2
  curl --fail --location --retry 3 "$url" --output "$archive"
  actual=$(shasum -a 256 "$archive" | awk '{print $1}')
  if [[ $actual != "$expected" ]]; then
    echo "$name SHA-256 mismatch: expected $expected, got $actual" >&2
    exit 1
  fi

  mkdir -p "$source"
  case "$url" in
    *.tar.gz|*.tgz) tar -xzf "$archive" -C "$source" --strip-components=1 ;;
    *.tar.xz) tar -xJf "$archive" -C "$source" --strip-components=1 ;;
    *) echo "Unsupported source archive format for $name: $url" >&2; exit 1 ;;
  esac

  echo "Building $name $version" >&2
  case "$name" in
    openssl)
      (cd "$source" && ./Configure darwin64-arm64-cc shared no-tests --prefix="$prefix" --openssldir="$prefix/ssl" --libdir=lib && make -j"$jobs" && make install_sw)
      ;;
    icu)
      configure=$(find "$source" -type f -path '*/source/configure' -print -quit)
      if [[ -z $configure ]]; then
        echo "ICU source/configure was not present in the pinned source archive" >&2
        exit 1
      fi
      (cd "${configure%/configure}" && ./configure --prefix="$prefix" --enable-shared --disable-static --disable-samples --disable-tests && make -j"$jobs" && make install)
      ;;
    lz4|zstd)
      (cd "$source" && make -j"$jobs" CC=clang && make install PREFIX="$prefix" CC=clang)
      ;;
    libxml2)
      (cd "$source" && ./configure --prefix="$prefix" --with-iconv --without-zlib --without-lzma --without-icu --without-python --without-readline --without-history --without-docs && make -j"$jobs" && make install)
      ;;
    libxslt)
      export PKG_CONFIG_PATH="$prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
      export CPPFLAGS="-I$prefix/include${CPPFLAGS:+ $CPPFLAGS}"
      export LDFLAGS="-L$prefix/lib${LDFLAGS:+ $LDFLAGS}"
      (cd "$source" && ./configure --prefix="$prefix" --without-python --without-crypto --without-plugins && make -j"$jobs" && make install)
      ;;
  esac
done < "$work_dir/dependencies.tsv"
