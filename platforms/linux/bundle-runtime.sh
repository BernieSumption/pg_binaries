#!/usr/bin/env bash
set -euo pipefail

[[ $# == 4 ]] || { echo "usage: $0 STAGED_ROOT DESTINATION POSTGRESQL_PREFIX CORE|EXTENSION" >&2; exit 2; }
root=$1 destination=$2 pg_prefix=$3 kind=$4
[[ $kind == CORE || $kind == EXTENSION ]] || exit 2
mkdir -p "$destination"

while :; do
  copied=0
  while IFS= read -r -d '' binary; do
    file -b "$binary" | grep -q ELF || continue
    while read -r name path; do
      case "$name" in
        linux-vdso*|ld-linux*|libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|libresolv.so*|libnss_*) continue ;;
        libpq.so*) [[ $kind == EXTENSION ]] && continue ;;
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
    done < <(ldd "$binary" 2>/dev/null | awk '$2 == "=>" {print $1, $3}')
  done < <(find "$root/bin" "$root/lib" -type f -print0 2>/dev/null)
  (( copied > 0 )) || break
done
