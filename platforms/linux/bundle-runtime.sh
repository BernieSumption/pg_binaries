#!/usr/bin/env bash
set -euo pipefail

[[ $# == 4 ]] || { echo "usage: $0 STAGED_ROOT DESTINATION POSTGRESQL_PREFIX CORE|EXTENSION" >&2; exit 2; }
root=$1 destination=$2 pg_prefix=$3 kind=$4
[[ $kind == CORE || $kind == EXTENSION ]] || exit 2
mkdir -p "$destination"

while :; do
  copied=0
  while IFS= read -r -d '' binary; do
    LC_ALL=C IFS= read -r -n4 magic < "$binary" || continue
    [[ $magic == $'\x7fELF' ]] || continue
    while read -r name path; do
      case "$name" in
        linux-vdso*|ld-linux*|libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|libresolv.so*|libnss_*) continue ;;
      esac
      [[ -e $root/lib/$name ]] && continue
      [[ ! -f $path && -e $destination/$name ]] && continue
      [[ -f $path ]] || { echo "Unresolved runtime dependency $name for $binary" >&2; exit 1; }
      case "$path" in "$pg_prefix"/lib/*|"$root"/lib/*) continue ;; esac
      target="$destination/$name"
      if [[ -e $target ]]; then
        cmp -s "$path" "$target" || { echo "Conflicting runtime dependency: $target and $path" >&2; exit 1; }
      else
        cp -L "$path" "$target"
        copied=$((copied + 1))
      fi
    done < <(ldd "$binary" 2>/dev/null | sed -n -E \
      -e 's/^[[:space:]]*([^[:space:]]+)[[:space:]]+=>[[:space:]]+(.*)[[:space:]]+\(0x[0-9a-fA-F]+\)$/\1 \2/p' \
      -e 's/^[[:space:]]*([^[:space:]]+)[[:space:]]+=>[[:space:]]+not found$/\1 NOT_FOUND/p')
  done < <(find "$root" -type f -print0)
  (( copied > 0 )) || break
done
