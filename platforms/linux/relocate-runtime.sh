#!/usr/bin/env bash
set -euo pipefail

[[ $# == 2 || $# == 3 ]] || { echo "usage: $0 STAGED_ROOT CORE|EXTENSION|POSTGIS [PRIVATE_LIBRARY_DIRECTORY]" >&2; exit 2; }
root=$1 kind=$2
private=${3:-runtime}
[[ $kind == CORE || $kind == EXTENSION || $kind == POSTGIS ]] || exit 2

if [[ $kind == CORE ]]; then
  while IFS= read -r -d '' elf; do
    LC_ALL=C IFS= read -r -n4 magic < "$elf" || continue
    [[ $magic == $'\x7fELF' ]] || continue
    case "$elf" in
      "$root/libexec/"*) path='$ORIGIN/../lib:$ORIGIN/../lib/runtime:$ORIGIN/../lib/glibc' ;;
      "$root/lib/runtime/"*) path='$ORIGIN:$ORIGIN/../glibc' ;;
      *) rel=$(realpath --relative-to="$(dirname "$elf")" "$root/lib"); path="\$ORIGIN/$rel:\$ORIGIN/$rel/runtime:\$ORIGIN/$rel/glibc" ;;
    esac
    patchelf --set-rpath "$path" "$elf"
  done < <(find "$root/libexec" -type f -print0; find "$root/lib" -path "$root/lib/glibc" -prune -o -type f -print0)
elif [[ $kind == EXTENSION ]]; then
  while IFS= read -r -d '' elf; do
    LC_ALL=C IFS= read -r -n4 magic < "$elf" || continue
    [[ $magic == $'\x7fELF' ]] || continue
    rel=$(realpath --relative-to="$(dirname "$elf")" "$root/lib")
    patchelf --set-rpath "\$ORIGIN:\$ORIGIN/$rel:\$ORIGIN/$rel/$private:\$ORIGIN/$rel/runtime:\$ORIGIN/$rel/glibc" "$elf"
  done < <(find "$root" -type f -print0)
else
  while IFS= read -r -d '' elf; do
    LC_ALL=C IFS= read -r -n4 magic < "$elf" || continue
    [[ $magic == $'\x7fELF' ]] || continue
    case "$elf" in
      "$root/lib/postgis-deps/"*) path='$ORIGIN' ;;
      *) path='$ORIGIN:$ORIGIN/postgis-deps' ;;
    esac
    patchelf --set-rpath "$path" "$elf"
  done < <(find "$root/lib" -type f -print0)
fi
